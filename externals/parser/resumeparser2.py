import google.generativeai as genai
from pdfminer.high_level import extract_text
from docx import Document
from datetime import datetime
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


class ResumeParser2:
        
    def extract_resume_text(file_path):
        """Extracts text from a resume file (PDF, DOCX, or DOC)."""
        try:
            if file_path.lower().endswith(".pdf"):
                return extract_text(file_path)
            elif file_path.lower().endswith(".docx"):
                doc = Document(file_path)
                return "\n".join([para.text for para in doc.paragraphs])
            elif file_path.lower().endswith(".doc"):
                temp_docx_path = os.path.splitext(file_path)[0] + ".docx"
                convert_doc_to_docx(file_path, temp_docx_path)
                doc = Document(temp_docx_path)
                return "\n".join([para.text for para in doc.paragraphs])
            else:
                print(f"Unsupported file format: {file_path}")
                return ""
        except Exception as e:
            print(f"Error extracting text from {file_path}: {e}")
            return ""

    def convert_doc_to_docx(doc_path, docx_path):
        """Converts a .doc file to .docx using unoconv."""
        try:
            import subprocess
            subprocess.run(["unoconv", "-f", "docx", "-o", docx_path, doc_path], check=True)
        except Exception as e:
            print(f"Error converting DOC to DOCX: {e}")

    def parse_resumes_in_batch(texts):
        """
        Uses Gemini to parse multiple resumes in a single API request.
        Returns a list of parsed resume data.
        """
        combined_prompt = (
            "You are an expert resume parser. Extract the following details for EACH resume:\n"
            "1. Name (full name exactly as shown)\n"
            "2. Email (complete address without spaces)\n"
            "3. Phone Number (with country code if available)\n"
            "4. Graduation Date (month and year of last degree completion in 'Month YYYY' format)\n"
            "5. Current Company Name (official legal name)\n"
            "6. Current Designation (exact job title)\n\n"
            "Return STRICT JSON array. Each object MUST follow:\n"
            "[\n"
            "  {\n"
            '    "name": "John Doe",\n'
            '    "email": "john@email.com",\n'
            '    "phoneNumber": "+11234567890",\n'
            '    "graduationDate": "May 2023",\n'
            '    "currentCompanyName": "Tech Corp",\n'
            '    "currentDesignation": "Software Engineer"\n'
            "  }\n"
            "]\n"
            "Important Rules:\n"
            "- Phone numbers must start with '+' followed by country code\n"
            "- Remove all spaces from emails\n"
            "- Use full month names (January, February etc.)\n"
            "- If information is missing, use 'Not Found'\n"
            "- Current company is the most recent/last mentioned job\n\n"
            "Resumes to parse:\n"
        )
        combined_prompt += "\n---\n".join([f"RESUME {i+1}:\n{text}" for i, text in enumerate(texts)])

        model = genai.GenerativeModel('gemini-pro')
        try:
            response = model.generate_content(combined_prompt)
            raw_response = response.text.strip()
        except Exception as e:
            print(f"Error generating Gemini response: {e}")
            return []

        # Clean response
        json_start = raw_response.find('[')
        json_end = raw_response.rfind(']') + 1
        if json_start != -1 and json_end != 0:
            raw_response = raw_response[json_start:json_end]

        # Validate JSON
        try:
            parsed_data = json.loads(raw_response)
            if not isinstance(parsed_data, list):
                raise ValueError("Top-level structure should be an array")
            return parsed_data
        except Exception as e:
            print(f"JSON parsing failed: {e}")
            print("Raw response:", raw_response)
            return []

    def calculate_years_of_experience(graduation_date):
        """Calculates experience from graduation date to current date."""
        if not graduation_date or graduation_date == "Not Found":
            return {"year": 0, "month": 0}
        
        try:
            grad_date = datetime.strptime(graduation_date, "%B %Y")
            current_date = datetime.now()
            
            if grad_date > current_date:
                return {"year": 0, "month": 0}
            
            total_months = (current_date.year - grad_date.year) * 12 + (current_date.month - grad_date.month)
            if total_months < 0:
                total_months += 12
            
            return {
                "year": total_months // 12,
                "month": total_months % 12
            }
        except Exception as e:
            print(f"Experience calculation error: {e}")
            return {"year": 0, "month": 0}

    def validate_phone_number(number):
        """Standardizes phone number format."""
        if not number or number == "Not Found":
            return "Not Found"
        
        # Remove all non-digit characters except leading +
        cleaned = re.sub(r'(?!^\+)\D', '', number)
        if cleaned.startswith('+'):
            return cleaned
        return f"+{cleaned}" if cleaned else "Not Found"

    def process_multiple_resumes(directory_path):
        """Processes all resumes in the given directory in a single API request."""
        supported_extensions = [".pdf", ".docx", ".doc"]
        files = sorted([f for f in os.listdir(directory_path) if os.path.splitext(f)[1].lower() in supported_extensions])
        
        if not files:
            print("No supported files found.")
            return []

        # Extract all resume texts
        resume_texts = []
        file_names = []
        for file in files:
            file_path = os.path.join(directory_path, file)
            print(f"Extracting text from: {file}")
            text = extract_resume_text(file_path)
            if text:
                resume_texts.append(text)
                file_names.append(file)
            else:
                print(f"Skipped {file} (no text extracted)")

        # Parse all resumes in one API request
        parsed_data_list = parse_resumes_in_batch(resume_texts)

        # Process parsed data
        all_parsed_data = []
        for i, parsed_data in enumerate(parsed_data_list):
            grad_date = parsed_data.get("graduationDate", "Not Found")
            years_of_experience = calculate_years_of_experience(grad_date)
            
            all_parsed_data.append({
                "file_name": file_names[i],
                "name": parsed_data.get("name", "Not Found"),
                "email": parsed_data.get("email", "Not Found").replace(" ", ""),
                "phone_number": validate_phone_number(parsed_data.get("phoneNumber")),
                "years_of_experience": years_of_experience,
                "current_company": parsed_data.get("currentCompanyName", "Not Found"),
                "current_designation": parsed_data.get("currentDesignation", "Not Found")
            })

        return all_parsed_data

    if __name__ == "__main__":
        resumes_directory = "resumes\candidate_cvs"
        parsed_resumes = process_multiple_resumes(resumes_directory)

        for idx, resume in enumerate(parsed_resumes, start=1):
            print(f"\nResume {idx}: {resume['file_name']}")
            print(f"Name: {resume['name']}")
            print(f"Email: {resume['email']}")
            print(f"Phone Number: {resume['phone_number']}")
            print("Years of Experience:")
            print(f"year: {resume['years_of_experience']['year']}")
            print(f"month: {resume['years_of_experience']['month']}")
            print(f"Current Company Name: {resume['current_company']}")
            print(f"Current Designation: {resume['current_designation']}")