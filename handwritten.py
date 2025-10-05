import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import os
import docx
import fitz  # PyMuPDF for PDF processing
from dotenv import load_dotenv

# FIX 1: The function needs to be called with parentheses ()
load_dotenv()

# --- Configuration ---
# This script looks for the API key in this order:
# 1. Streamlit Secrets (for when you deploy your app)
# 2. An environment variable named "GEMINI_API_KEY" (for local development)

api_key = None
try:
    # Ideal for deployment: set a secret named GEMINI_API_KEY
    api_key = st.secrets["GEMINI_API_KEY"]
except (FileNotFoundError, KeyError):
    # Fallback for local development
    api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
else:
    # FIX 2: Updated the error message to be consistent with the code
    st.error("Google API Key not found. Please set it as a Streamlit secret or as a 'GEMINI_API_KEY' environment variable in your .env file.")
    # Stop the app from running further if no key is found
    st.stop()


# --- Gemini API Call Function ---
def analyze_image(image_bytes, prompt, image_format):
    """
    Sends the image and a prompt to the Gemini API and returns the response.
    """
    try:
        # FIX 3: Corrected the model name to a valid, powerful vision model
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        # The content for multi-modal input is a list of parts.
        image_part = {
            "mime_type": f"image/{image_format.lower()}",
            "data": image_bytes
        }
        
        # Pass the prompt and image together in a list
        response = model.generate_content([prompt, image_part])
        return response.text
    except Exception as e:
        st.error(f"An error occurred while calling the Gemini API: {e}")
        return None

# --- Helper function to create DOCX file ---
def create_docx_bytes(content):
    """Creates a DOCX file in memory from a string and returns its bytes."""
    doc = docx.Document()
    doc.add_paragraph(content)
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio.getvalue()

# --- UI Layout ---
st.set_page_config(layout="wide", page_title="Handwritten Document Analyzer")

st.title("Handwritten Document Analyzer 📄✍️")
st.markdown("Upload a handwritten note (image or PDF), and let Gemini AI transcribe and summarize it for you.")

# 1. File Uploader - Now accepts PDF
uploaded_file = st.file_uploader("1. Upload Your Document", type=["jpg", "jpeg", "png", "pdf"])

# Define the prompt outside the logic branches so it's reusable
prompt = """
Based on the provided image of a handwritten document, perform the following two tasks:
1.  **Transcript:** Provide a full transcript of all the text visible in the document. Preserve the original line breaks and formatting as much as possible.
2.  **Summary:** After the transcript, provide a concise summary of the document's content.

Structure your response exactly as follows, using Markdown formatting:
### Transcript
---
[Your full transcript here]

### Summary
---
[Your summary here]
"""

if uploaded_file is not None:
    # Handle based on file type
    file_type = uploaded_file.type

    # --- IMAGE FILE LOGIC ---
    if file_type in ["image/jpeg", "image/png"]:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Document", width=300) 

        img_byte_arr = io.BytesIO()
        image_format = image.format
        image.save(img_byte_arr, format=image_format)
        image_bytes = img_byte_arr.getvalue()

        if st.button("Analyze Document", use_container_width=True, type="primary"):
            with st.spinner("Gemini is analyzing your document, please wait..."):
                analysis_result = analyze_image(image_bytes, prompt, image_format)

                if analysis_result:
                    st.markdown("## Analysis Results")
                    st.markdown(analysis_result)

                    docx_bytes = create_docx_bytes(analysis_result)
                    st.download_button(
                        label="Download Analysis as DOCX",
                        data=docx_bytes,
                        file_name="analysis_result.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                else:
                    st.error("Failed to get a response from the AI. Please try again.")

    # --- PDF FILE LOGIC ---
    elif file_type == "application/pdf":
        pdf_bytes = uploaded_file.getvalue()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        st.info(f"PDF uploaded with {len(doc)} pages. Click 'Analyze' to process all pages.")

        if st.button("Analyze Full PDF", use_container_width=True, type="primary"):
            all_results = []
            with st.spinner(f"Analyzing {len(doc)} pages... This may take a moment."):
                for i, page in enumerate(doc):
                    st.markdown(f"--- \n ### Analyzing Page {i + 1}")
                    
                    # Render page to an image
                    pix = page.get_pixmap(dpi=200) # Higher DPI for better quality
                    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    st.image(image, caption=f"Page {i + 1}", width=300)
                    
                    # Convert PIL image to bytes for the API
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format="PNG")
                    image_bytes = img_byte_arr.getvalue()

                    # Call the API for the current page
                    analysis_result = analyze_image(image_bytes, prompt, "PNG")
                    
                    if analysis_result:
                        st.markdown(analysis_result)
                        page_result_for_doc = f"## Results for Page {i + 1}\n\n{analysis_result}"
                        all_results.append(page_result_for_doc)
                    else:
                        st.error(f"Failed to get a response for Page {i + 1}.")
                        all_results.append(f"## Results for Page {i + 1}\n\n[ANALYSIS FAILED]")
            
            if all_results:
                st.markdown("--- \n ## ✅ All Pages Processed")
                final_analysis = "\n\n".join(all_results)
                
                docx_bytes = create_docx_bytes(final_analysis)
                st.download_button(
                    label="Download Full Analysis as DOCX",
                    data=docx_bytes,
                    file_name="full_pdf_analysis.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )

