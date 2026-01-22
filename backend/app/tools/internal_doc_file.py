from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

DATA_FOLDER = os.path.join(BASE_DIR, "data")

def list_documents():
    return [
        f for f in os.listdir(DATA_FOLDER)
        if os.path.isfile(os.path.join(DATA_FOLDER, f))
    ]


def load_document_file(file_name: str):
    file_path = os.path.join(DATA_FOLDER, file_name)

    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_name}"}

    with open(file_path, "rb") as f:
        return {"file_name": file_name}



def generate_briefing_pdf(summary: str, takeaways: str, table: str):
    """Generate a professionally formatted briefing PDF."""
    
    output_path = os.path.join(DATA_FOLDER, "briefing_report.pdf")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    story = []

    # --- TITLE ---
    title = Paragraph("<b>INTERNAL KNOWLEDGE BRIEFING REPORT</b>", styles["Title"])
    timestamp = Paragraph(f"<i>Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M')}</i>", styles["Normal"])

    story.append(title)
    story.append(timestamp)
    story.append(Spacer(1, 0.3 * inch))

    # --- EXECUTIVE SUMMARY ---
    story.append(Paragraph("<b>EXECUTIVE SUMMARY</b>", styles["Heading2"]))
    for paragraph in summary.split("\n"):
        if paragraph.strip():
            story.append(Paragraph(paragraph, styles["BodyText"]))
            story.append(Spacer(1, 0.1 * inch))

    story.append(Spacer(1, 0.3 * inch))

    # --- KEY TAKEAWAYS ---
    story.append(Paragraph("<b>KEY TAKEAWAYS</b>", styles["Heading2"]))

    for line in takeaways.split("\n"):
        if line.strip():
            bullet = f"• {line.strip()}"
            story.append(Paragraph(bullet, styles["BodyText"]))
            story.append(Spacer(1, 0.1 * inch))

    story.append(Spacer(1, 0.3 * inch))

    # --- COMPARATIVE TABLE ---
    story.append(Paragraph("<b>COMPARATIVE TABLE / DETAILS</b>", styles["Heading2"]))
    
    # Convert table text to structured rows
    parsed_rows = []
    for line in table.split("\n"):
        if "|" in line:
            parts = [col.strip() for col in line.split("|") if col.strip()]
            if len(parts) >= 2:
                wrapped = [Paragraph(col, cell_style) for col in parts]
                parsed_rows.append(wrapped)

    # Create clean table
    tbl = Table(parsed_rows, colWidths=[2.5*inch, 3.8*inch])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),     # IMPORTANT: prevents overlap
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(tbl)

    # Build PDF
    doc.build(story)

    return {"pdf_path": output_path}