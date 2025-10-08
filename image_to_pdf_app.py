import streamlit as st
from PIL import Image
import io
from fpdf2 import FPDF
import tempfile
import os


def images_to_pdf(images, output_path):
    """Convert multiple images to a single PDF file."""
    pdf = FPDF()

    for img in images:
        # Open image using PIL
        pil_img = Image.open(img)

        # Convert RGBA to RGB if necessary
        if pil_img.mode == 'RGBA':
            pil_img = pil_img.convert('RGB')

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            pil_img.save(tmp_file.name, 'JPEG')
            tmp_path = tmp_file.name

        # Get image dimensions
        width, height = pil_img.size

        # Calculate PDF page size (A4 or image size)
        pdf.add_page()

        # Calculate dimensions to fit page while maintaining aspect ratio
        page_width = 210  # A4 width in mm
        page_height = 297  # A4 height in mm

        # Calculate scaling factor
        width_ratio = page_width / (width * 0.264583)  # Convert pixels to mm
        height_ratio = page_height / (height * 0.264583)
        ratio = min(width_ratio, height_ratio)

        img_width = width * 0.264583 * ratio
        img_height = height * 0.264583 * ratio

        # Center the image on the page
        x = (page_width - img_width) / 2
        y = (page_height - img_height) / 2

        pdf.image(tmp_path, x=x, y=y, w=img_width, h=img_height)

        # Clean up temporary file
        os.unlink(tmp_path)

    pdf.output(output_path)


def main():
    st.set_page_config(page_title="Image to PDF Converter", page_icon="📄")

    st.title("📄 Image to PDF Converter")
    st.write("Upload multiple images and convert them into a single PDF file.")

    # File uploader
    uploaded_files = st.file_uploader(
        "Choose images",
        type=['png', 'jpg', 'jpeg', 'gif', 'bmp'],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.write(f"**{len(uploaded_files)} image(s) uploaded**")

        # Display thumbnails
        cols = st.columns(min(len(uploaded_files), 4))
        for idx, uploaded_file in enumerate(uploaded_files):
            with cols[idx % 4]:
                image = Image.open(uploaded_file)
                st.image(image, caption=uploaded_file.name, use_container_width=True)

        # PDF filename input - default to first uploaded file's name
        default_name = os.path.splitext(uploaded_files[0].name)[0]
        pdf_filename = st.text_input(
            "PDF filename (without extension)",
            value=default_name
        )

        # Convert button
        if st.button("Convert to PDF", type="primary"):
            try:
                with st.spinner("Converting images to PDF..."):
                    # Create temporary PDF file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                        output_path = tmp_pdf.name

                    # Reset file pointers
                    for f in uploaded_files:
                        f.seek(0)

                    # Convert images to PDF
                    images_to_pdf(uploaded_files, output_path)

                    # Read the PDF file
                    with open(output_path, 'rb') as f:
                        pdf_data = f.read()

                    # Clean up temporary file
                    os.unlink(output_path)

                    st.success("✅ PDF created successfully!")

                    # Download button
                    st.download_button(
                        label="📥 Download PDF",
                        data=pdf_data,
                        file_name=f"{pdf_filename}.pdf",
                        mime="application/pdf"
                    )

            except Exception as e:
                st.error(f"Error creating PDF: {str(e)}")
    else:
        st.info("👆 Please upload one or more images to get started.")


if __name__ == "__main__":
    main()
