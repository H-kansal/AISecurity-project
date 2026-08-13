import asyncio
import difflib
import hashlib
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

def generate_pdf(title: str, content: str) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, title[:80])
    c.setFont("Helvetica", 10)
    y = height - 80
    for line in content.split("\n"):
        for chunk in [line[i:i + 95] for i in range(0, max(len(line), 1), 95)]:
            if y < 60:
                c.showPage()
                y = height - 50
            c.drawString(50, y, chunk)
            y -= 14
    c.save()
    buffer.seek(0)
    return buffer.read()


def generate_json_report(topic: str, report: str, report_id: str, created_at: datetime) -> dict:
    return {
        "report_id": report_id,
        "topic": topic,
        "report": report,
        "created_at": created_at.isoformat(),
        "word_count": len(report.split()),
        "checksum": hashlib.md5(report.encode()).hexdigest(),
        
    }