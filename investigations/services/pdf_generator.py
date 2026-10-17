import os
import re
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path

from django.conf import settings
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute total page count and render
    running headers and footers on every page.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(54, 750, "RED THREAD | INTELLIGENCE RESEARCH REPORT")
            self.drawRightString(612 - 54, 750, "CONFIDENTIAL / RESEARCH GRADE")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(54, 744, 612 - 54, 744)

        # Footer (All pages)
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(54, 50, 612 - 54, 50)
        self.drawString(54, 38, "RED THREAD OSINT INTEL PLATFORM • ZERO-COST DETERMINISTIC INFERENCE")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 54, 38, page_str)
        self.restoreState()


def clean_markdown_for_pdf(text: str) -> str:
    """
    Removes raw asterisks, wiki headers, and formats text safely for ReportLab XML parser.
    """
    if not text:
        return ""
    # Strip raw wiki headers == Header ==
    text = re.sub(r'==+\s*([^=]+)\s*==+', r'\1', text)
    # Convert **bold** to <b>bold</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # Convert *italic* to <i>italic</i>
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    # Strip any remaining lone asterisks
    text = text.replace('*', '')
    # Escape XML entities except our tags
    text = text.replace('&', '&amp;')
    # Fix back converted tags
    text = text.replace('&amp;lt;', '<').replace('&amp;gt;', '>')
    # Clean up linebreaks
    return text.strip()


class PDFReportGenerator:
    """
    Generates academic/intelligence grade multi-page research PDFs with ReportLab,
    saving a copy locally to the `reports/` folder and returning binary data for download.
    """

    def __init__(self):
        self.reports_dir = Path(settings.BASE_DIR).parent / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, investigation) -> tuple[bytes, str, Path]:
        """
        Generates PDF for the given investigation.
        Returns (pdf_bytes, filename, file_path).
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=60,
        )

        styles = getSampleStyleSheet()

        # Custom typography styles
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8,
        )

        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#475569"),
            spaceAfter=14,
        )

        section_heading_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#991b1b"),
            spaceBefore=14,
            spaceAfter=6,
            keepWithNext=True,
        )

        sub_heading_style = ParagraphStyle(
            'SubHeading',
            parent=styles['Heading3'],
            fontName='Helvetica-Bold',
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        )

        body_style = ParagraphStyle(
            'ReportBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=8,
        )

        finding_style = ParagraphStyle(
            'FindingItem',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13.5,
            textColor=colors.HexColor("#0f172a"),
        )

        table_header_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=colors.white,
        )

        table_body_style = ParagraphStyle(
            'TableBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1e293b"),
        )

        meta_label_style = ParagraphStyle(
            'MetaLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748b"),
        )

        meta_val_style = ParagraphStyle(
            'MetaVal',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0f172a"),
        )

        story = []

        # 1. Header Banner & Title Block
        story.append(Paragraph("RED THREAD INTELLIGENCE & RESEARCH DOSSIER", ParagraphStyle(
            'BrandTag',
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#dc2626"),
            spaceAfter=4,
        )))
        story.append(Paragraph(clean_markdown_for_pdf(investigation.title), title_style))
        story.append(Paragraph(f"Research Question: {clean_markdown_for_pdf(investigation.research_question)}", subtitle_style))

        # Metadata Table
        report = getattr(investigation, 'report', None)
        mode_used = report.generated_by_mode if report else investigation.mode
        created_str = (report.created_at if report else investigation.created_at).strftime("%B %d, %Y - %H:%M UTC")

        meta_data = [
            [
                Paragraph("<b>INVESTIGATION ID:</b>", meta_label_style),
                Paragraph(str(investigation.id)[:18] + "...", meta_val_style),
                Paragraph("<b>DATE OF DOSSIER:</b>", meta_label_style),
                Paragraph(created_str, meta_val_style),
            ],
            [
                Paragraph("<b>INFERENCE ENGINE:</b>", meta_label_style),
                Paragraph(mode_used, meta_val_style),
                Paragraph("<b>PRIMARY SOURCES:</b>", meta_label_style),
                Paragraph(f"{investigation.sources.count()} Verified Public Records", meta_val_style),
            ],
            [
                Paragraph("<b>EXTRACTED CLAIMS:</b>", meta_label_style),
                Paragraph(f"{investigation.claims.count()} Assertions Tracked", meta_val_style),
                Paragraph("<b>IDENTIFIED ENTITIES:</b>", meta_label_style),
                Paragraph(f"{investigation.entities.count()} Named Participants", meta_val_style),
            ]
        ]
        meta_table = Table(meta_data, colWidths=[110, 140, 110, 144])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 14))

        # 2. Executive Summary
        if report and report.executive_summary:
            story.append(Paragraph("1. Executive Summary", section_heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#991b1b"), spaceAfter=6))
            for para in report.executive_summary.split('\n\n'):
                if para.strip():
                    story.append(Paragraph(clean_markdown_for_pdf(para), body_style))
            story.append(Spacer(1, 10))

        # 3. Foundational Orientation & First-Principles Guide
        if report and report.topic_primer:
            story.append(Paragraph("2. Foundational Orientation & First-Principles Guide", section_heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#991b1b"), spaceAfter=6))
            
            primer_sections = report.topic_primer.split('\n\n')
            for sec in primer_sections:
                sec_clean = sec.strip()
                if not sec_clean:
                    continue
                if sec_clean.startswith('### '):
                    lines = sec_clean.split('\n')
                    h_text = lines[0].replace('### ', '').strip()
                    story.append(Paragraph(clean_markdown_for_pdf(h_text), sub_heading_style))
                    for line in lines[1:]:
                        if line.strip():
                            story.append(Paragraph(clean_markdown_for_pdf(line), body_style))
                else:
                    story.append(Paragraph(clean_markdown_for_pdf(sec_clean), body_style))
            story.append(Spacer(1, 10))

        # 4. Key Findings & Empirical Claims
        claims = list(investigation.claims.all()[:10])
        if claims:
            story.append(Paragraph("3. Verified Key Findings & Evidentiary Claims", section_heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#991b1b"), spaceAfter=6))

            claims_data = [[
                Paragraph("<b>#</b>", table_header_style),
                Paragraph("<b>Factual Assertion / Claim</b>", table_header_style),
                Paragraph("<b>Status</b>", table_header_style),
                Paragraph("<b>Citations</b>", table_header_style)
            ]]

            for idx, c in enumerate(claims, 1):
                c_sources = list(c.sources.all())
                citations_str = ", ".join([s.citation_key for s in c_sources]) if c_sources else "-"
                status_color = "#15803d" if c.evidence_status == 'SUPPORTED' else "#b45309" if c.evidence_status == 'DISPUTED' else "#64748b"
                
                claims_data.append([
                    Paragraph(f"{idx:02d}", finding_style),
                    Paragraph(clean_markdown_for_pdf(c.claim_text), finding_style),
                    Paragraph(f"<font color='{status_color}'><b>{c.evidence_status}</b></font>", finding_style),
                    Paragraph(f"[{citations_str}]", finding_style)
                ])

            claims_table = Table(claims_data, colWidths=[24, 340, 80, 60])
            claims_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(claims_table)
            story.append(Spacer(1, 12))

        # 5. Supporting Evidence Synthesis
        if report and report.supporting_evidence_synthesis:
            story.append(Paragraph("4. Supporting Evidence Synthesis & Technical Breakdown", section_heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#991b1b"), spaceAfter=6))

            for block in report.supporting_evidence_synthesis.split('\n\n'):
                block_clean = block.strip()
                if not block_clean:
                    continue
                if block_clean.startswith('### '):
                    lines = block_clean.split('\n')
                    story.append(Paragraph(clean_markdown_for_pdf(lines[0].replace('### ', '')), sub_heading_style))
                    for line in lines[1:]:
                        if line.strip():
                            story.append(Paragraph(clean_markdown_for_pdf(line), body_style))
                else:
                    story.append(Paragraph(clean_markdown_for_pdf(block_clean), body_style))
            story.append(Spacer(1, 10))

        # 6. Entity Dossier
        entities = list(investigation.entities.all()[:12])
        if entities:
            story.append(Paragraph("5. Entity Network & Stakeholder Registry", section_heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#991b1b"), spaceAfter=6))

            ent_data = [[
                Paragraph("<b>Entity Name</b>", table_header_style),
                Paragraph("<b>Classification</b>", table_header_style),
                Paragraph("<b>Role & Monitored Context</b>", table_header_style),
            ]]
            for e in entities:
                ent_data.append([
                    Paragraph(f"<b>{clean_markdown_for_pdf(e.name)}</b>", table_body_style),
                    Paragraph(e.entity_type, table_body_style),
                    Paragraph(clean_markdown_for_pdf(e.description or "Monitored stakeholder"), table_body_style)
                ])

            ent_table = Table(ent_data, colWidths=[120, 90, 294])
            ent_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(ent_table)
            story.append(Spacer(1, 12))

        # 7. Contradictions & Competing Explanations
        if report and report.contradictions_and_disagreements:
            story.append(Paragraph("6. Contradictions & Competing Explanations", section_heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#991b1b"), spaceAfter=6))
            story.append(Paragraph(clean_markdown_for_pdf(report.contradictions_and_disagreements), body_style))
            story.append(Spacer(1, 10))

        # 8. Unresolved Questions & Next Directions
        if report and (report.unresolved_questions or report.further_research_directions):
            story.append(Paragraph("7. Critical Intelligence Gaps & Further Directions", section_heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#991b1b"), spaceAfter=6))

            if report.unresolved_questions:
                story.append(Paragraph("Unresolved Questions & Knowledge Gaps:", sub_heading_style))
                story.append(Paragraph(clean_markdown_for_pdf(report.unresolved_questions), body_style))

            if report.further_research_directions:
                story.append(Paragraph("Next Investigative Vectors:", sub_heading_style))
                story.append(Paragraph(clean_markdown_for_pdf(report.further_research_directions), body_style))
            story.append(Spacer(1, 10))

        # 9. Source Repository Table
        sources = list(investigation.sources.all()[:12])
        if sources:
            story.append(Paragraph("8. Primary Evidentiary Sources & Documentation", section_heading_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#991b1b"), spaceAfter=6))

            src_data = [[
                Paragraph("<b>Key</b>", table_header_style),
                Paragraph("<b>Source Title / Publication</b>", table_header_style),
                Paragraph("<b>URL / Repository Reference</b>", table_header_style),
            ]]
            for s in sources:
                src_data.append([
                    Paragraph(f"[{s.citation_key}]", table_body_style),
                    Paragraph(f"<b>{clean_markdown_for_pdf(s.title)}</b><br/><font color='#64748b'>{s.source_name}</font>", table_body_style),
                    Paragraph(f"<font color='#2563eb'>{s.url[:60]}...</font>" if len(s.url) > 60 else f"<font color='#2563eb'>{s.url}</font>", table_body_style),
                ])

            src_table = Table(src_data, colWidths=[36, 268, 200])
            src_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(src_table)

        # Build PDF using NumberedCanvas
        doc.build(story, canvasmaker=NumberedCanvas)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        # Generate safe filename and save to local reports folder
        clean_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', investigation.title).strip().replace(' ', '_')[:40]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{clean_title}_{timestamp}.pdf"
        file_path = self.reports_dir / filename

        try:
            with open(file_path, 'wb') as f:
                f.write(pdf_bytes)
            logger.info(f"Report PDF successfully saved to disk at {file_path}")
        except Exception as e:
            logger.error(f"Failed to save PDF to {file_path}: {e}")

        return pdf_bytes, filename, file_path
