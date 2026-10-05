"""
FILE: src/pdf_generator.py
PURPOSE: PDF Health Report Generator using ReportLab
GROUP: F25PROJECT664B0
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from io import BytesIO
from datetime import datetime
import logging

log = logging.getLogger(__name__)

# Colour palette consistent with the frontend theme
BLUE       = colors.HexColor("#1F4E79")
LIGHT_BLUE = colors.HexColor("#2E75B6")
LIGHT_BG   = colors.HexColor("#D6E4F0")
RED        = colors.HexColor("#CC0000")
AMBER      = colors.HexColor("#B7791F")
GREEN      = colors.HexColor("#276749")
GREY       = colors.HexColor("#404040")
WHITE      = colors.white

# Triage level to colour mapping
TRIAGE_COLORS = {
    "Low":    GREEN,
    "Medium": AMBER,
    "High":   RED,
}

# Triage level to label mapping
TRIAGE_LABELS = {
    "Low":    "Self-Care",
    "Medium": "Visit GP",
    "High":   "Urgent Care",
}


def generate_pdf_from_data(data: dict) -> bytes:
    """
    Builds a complete PDF health report from the prediction result.
    Returns raw bytes that FastAPI sends back as application/pdf.

    This function accepts the full result payload directly from the
    frontend so it works for both guest and registered user sessions.
    """
    buffer = BytesIO()

    try:
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )

        styles = getSampleStyleSheet()
        story  = []

        # ── Custom styles ──────────────────────────────────────────────
        title_style = ParagraphStyle(
            "CustomTitle",
            parent    = styles["Title"],
            fontSize  = 22,
            textColor = BLUE,
            spaceAfter= 6,
            alignment = TA_CENTER,
            fontName  = "Helvetica-Bold",
        )
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent    = styles["Normal"],
            fontSize  = 11,
            textColor = LIGHT_BLUE,
            spaceAfter= 4,
            alignment = TA_CENTER,
            fontName  = "Helvetica",
        )
        section_style = ParagraphStyle(
            "Section",
            parent    = styles["Heading2"],
            fontSize  = 13,
            textColor = BLUE,
            spaceBefore=14,
            spaceAfter= 6,
            fontName  = "Helvetica-Bold",
        )
        body_style = ParagraphStyle(
            "Body",
            parent    = styles["Normal"],
            fontSize  = 10,
            textColor = GREY,
            spaceAfter= 4,
            leading   = 15,
            alignment = TA_JUSTIFY,
            fontName  = "Helvetica",
        )
        disclaimer_style = ParagraphStyle(
            "Disclaimer",
            parent    = styles["Normal"],
            fontSize  = 9,
            textColor = colors.HexColor("#888888"),
            spaceAfter= 4,
            leading   = 13,
            alignment = TA_JUSTIFY,
            fontName  = "Helvetica-Oblique",
        )

        # ── Header ─────────────────────────────────────────────────────
        story.append(Paragraph("AI-Powered Smart Health Assistant", title_style))
        story.append(Paragraph("Health Assessment Report", subtitle_style))
        story.append(Paragraph("Virtual University of Pakistan | Group: F25PROJECT664B0", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=2, color=LIGHT_BLUE, spaceAfter=12))

        # ── Report metadata ────────────────────────────────────────────
        generated_at = data.get("generated_at", datetime.now().isoformat())
        try:
            dt = datetime.fromisoformat(generated_at)
            date_str = dt.strftime("%d %B %Y, %I:%M %p")
        except Exception:
            date_str = generated_at

        meta_data = [
            ["Report ID",       data.get("query_id", "N/A")],
            ["Patient Name",    data.get("patient_name", "Patient")],
            ["Generated On",    date_str],
        ]
        meta_table = Table(meta_data, colWidths=[5*cm, 12*cm])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (0,-1), LIGHT_BG),
            ("TEXTCOLOR",   (0,0), (0,-1), BLUE),
            ("FONTNAME",    (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTNAME",    (1,0), (1,-1), "Helvetica"),
            ("FONTSIZE",    (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.HexColor("#F2F2F2"), WHITE]),
            ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
            ("LEFTPADDING",  (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING",   (0,0), (-1,-1), 6),
            ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 12))

        # ── Submitted symptoms ─────────────────────────────────────────
        story.append(Paragraph("Submitted Symptoms", section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BG, spaceAfter=6))
        symptoms_text = data.get("symptoms", "Not provided")
        story.append(Paragraph(symptoms_text, body_style))
        story.append(Spacer(1, 8))

        # ── Triage level ───────────────────────────────────────────────
        triage_raw   = data.get("triage_level", "Medium")
        triage_color = TRIAGE_COLORS.get(triage_raw, AMBER)
        triage_label = TRIAGE_LABELS.get(triage_raw, triage_raw)
        triage_explanation = data.get("triage_explanation", "")

        story.append(Paragraph("Triage Assessment", section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BG, spaceAfter=6))

        triage_data = [["Triage Level", triage_label], ["Recommended Action", triage_explanation or "See recommended specialist."]]
        triage_table = Table(triage_data, colWidths=[5*cm, 12*cm])
        triage_table.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (0,-1), LIGHT_BG),
            ("TEXTCOLOR",    (0,0), (0,-1), BLUE),
            ("TEXTCOLOR",    (1,0), (1,0), triage_color),
            ("FONTNAME",     (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTNAME",     (1,0), (1,-1), "Helvetica"),
            ("FONTNAME",     (1,0), (1,0), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,-1), 10),
            ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS",(0,0),(-1,-1), [colors.HexColor("#F2F2F2"), WHITE]),
            ("LEFTPADDING",  (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING",   (0,0), (-1,-1), 6),
            ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ]))
        story.append(triage_table)
        story.append(Spacer(1, 8))

        # ── Top predicted conditions ───────────────────────────────────
        conditions = data.get("conditions", [])
        if conditions:
            story.append(Paragraph("Predicted Conditions", section_style))
            story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BG, spaceAfter=6))

            cond_header = [["#", "Condition", "Confidence", "Description"]]
            cond_rows   = []
            for i, c in enumerate(conditions[:3], 1):
                cond_rows.append([
                    str(i),
                    str(c.get("name", "")),
                    f"{c.get('confidence', 0)}%",
                    str(c.get("description", ""))[:120],
                ])

            cond_table = Table(cond_header + cond_rows, colWidths=[1*cm, 4*cm, 2.5*cm, 9.5*cm])
            cond_table.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,0), BLUE),
                ("TEXTCOLOR",    (0,0), (-1,0), WHITE),
                ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTNAME",     (0,1), (-1,-1),"Helvetica"),
                ("FONTSIZE",     (0,0), (-1,-1), 9),
                ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.HexColor("#F2F2F2"), WHITE]),
                ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
                ("LEFTPADDING",  (0,0), (-1,-1), 8),
                ("RIGHTPADDING", (0,0), (-1,-1), 8),
                ("TOPPADDING",   (0,0), (-1,-1), 6),
                ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ]))
            story.append(cond_table)
            story.append(Spacer(1, 8))

        # ── Recommended specialist ─────────────────────────────────────
        specialist = data.get("recommended_specialist", "General Physician")
        story.append(Paragraph("Recommended Specialist", section_style))
        story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BG, spaceAfter=6))
        story.append(Paragraph(f"Based on your symptoms, you are advised to consult a <b>{specialist}</b>.", body_style))
        story.append(Spacer(1, 8))

        # ── Key symptoms ───────────────────────────────────────────────
        key_symptoms = data.get("key_symptoms", [])
        if key_symptoms:
            story.append(Paragraph("Key Symptoms That Influenced This Result", section_style))
            story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BG, spaceAfter=6))
            story.append(Paragraph(", ".join(key_symptoms), body_style))
            story.append(Spacer(1, 8))

        # ── Summary ────────────────────────────────────────────────────
        summary = data.get("summary", "")
        if summary:
            story.append(Paragraph("Summary", section_style))
            story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BG, spaceAfter=6))
            story.append(Paragraph(summary, body_style))
            story.append(Spacer(1, 8))

        # ── Disclaimer ─────────────────────────────────────────────────
        story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BG, spaceAfter=8))
        story.append(Paragraph("Medical Disclaimer", section_style))
        story.append(Paragraph(
            "This report is generated by an AI system and is intended for informational "
            "purposes only. It does NOT constitute a medical diagnosis, professional medical "
            "advice, or a substitute for consultation with a qualified healthcare professional. "
            "Always consult a licensed doctor before making any health-related decisions. "
            "In case of a medical emergency, contact your nearest hospital immediately.",
            disclaimer_style
        ))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "AI-Powered Smart Health Assistant | Virtual University of Pakistan | Group: F25PROJECT664B0",
            disclaimer_style
        ))

        # ── Build the PDF ──────────────────────────────────────────────
        doc.build(story)

        # Get the bytes from the buffer
        pdf_bytes = buffer.getvalue()

        if not pdf_bytes:
            log.error("PDF buffer is empty after build.")
            return b""

        log.info(f"PDF generated successfully. Size: {len(pdf_bytes)} bytes.")
        return pdf_bytes

    except Exception as e:
        log.error(f"PDF generation failed: {e}")
        raise
    finally:
        buffer.close()