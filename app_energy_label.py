from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.platypus import Flowable
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from flask_babel import _


from app_report_exporter import get_CSN_73_6161_classification
from app_report_exporter import get_CSN_73_6161_word_classification
class EnergyLabel(Flowable):
    def __init__(self, adhesion_rate: float, width=50, spacing=0, bar_height=20, arrow_tip=20):
        super().__init__()
        self.rating = get_CSN_73_6161_classification(adhesion_rate) 
        self.word_rating = get_CSN_73_6161_word_classification(adhesion_rate) 
        self.adhesion_rate = adhesion_rate
        self.width = width
        self.bar_height = bar_height
        self.spacing = spacing
        self.arrow_tip = arrow_tip

        self.classes = [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            _("Unclassifiable"),
        ]

        self.colors = [
            colors.HexColor("#11a64a"),
            colors.HexColor("#56b347"),
            colors.HexColor("#b7d432"),
            colors.HexColor("#f4e600"),
            colors.HexColor("#f8b415"),
            colors.HexColor("#f37021"),
            colors.HexColor("#ed1c24"),
            colors.HexColor("#160001"),
        ]

        self.height = len(self.classes)*(self.bar_height+self.spacing)

    def draw_arrow(self, c, x, y, width, height, color, text):
        c.setFillColor(color)
        c.setStrokeColor(color)

        arrow_tip = self.arrow_tip

        path = c.beginPath()
        path.moveTo(x, y)
        path.lineTo(x + width - arrow_tip, y)
        path.lineTo(x + width, y + height / 2)
        path.lineTo(x + width - arrow_tip, y + height)
        path.lineTo(x, y + height)
        path.close()

        c.drawPath(path, fill=1, stroke=0)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(x + 15, y + height / 2 - 6, text)
    def draw_arrow_left(self, c, x, y, width, height, color, text):
        c.setFillColor(color)
        c.setStrokeColor(color)

        arrow_tip = self.arrow_tip

        path = c.beginPath()
        path.moveTo(x, y)
        path.lineTo(x + width - arrow_tip, y)
        path.lineTo(x + width - arrow_tip, y + height)
        path.lineTo(x, y + height)
        path.lineTo(x - arrow_tip, y + height/2)
        path.close()

        c.drawPath(path, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(x + 15, y + height / 2 - 6, text)

    def draw_left_box(self, c):
        box_width = 130
        box_height = (self.bar_height+self.spacing)*len(self.classes)-self.spacing

        c.setFillColor(colors.white)
        c.setStrokeColor(colors.black)
        c.rect(0, self.height - box_height, box_width, box_height, fill=1)

        c.setFillColor(colors.black)
        c.setFont("Helvetica", 12)
        c.drawCentredString(box_width / 2,
                            self.height - box_height * 1.25 / 5,
                            _("Adhesion")
        )
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(box_width / 2,
                            self.height - box_height * 2 / 5,
                            f"{self.adhesion_rate} %")

        c.setFont("Helvetica", 12)
        c.drawCentredString(box_width / 2,
                            self.height - box_height * 3.25 / 5,
                            _("Rating"))
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(box_width / 2,
                            self.height - box_height * 4 / 5,
                            self.word_rating)

        return box_width + 15  # spacing before arrows
    def draw(self):
        c = self.canv

        offset_x = self.draw_left_box(c)

        bar_height = self.bar_height
        spacing = self.spacing
        start_y = self.height - bar_height

        # dra

        for i, (cls, col) in enumerate(zip(self.classes, self.colors)):
            y = start_y - i * (bar_height + spacing)
            width = self.width + i * 20
            self.draw_arrow(c, offset_x, y, width, bar_height, col, cls)

        # Draw highlighted rating on right
        if self.rating in self.classes:
            idx = self.classes.index(self.rating)
            y = start_y - idx * (bar_height + spacing)
            width = self.width + len(self.classes)*self.arrow_tip

            self.draw_arrow_left(
                c,
                offset_x + width,
                y,
                155,
                bar_height,
                self.colors[idx],
                self.rating,
            )

doc = SimpleDocTemplate("energy_report.pdf", pagesize=A4)
elements = []

# elements.append(EnergyLabel("C"))
# elements.append(EnergyLabel("Unclassifiable"))
elements.append(EnergyLabel(96))
elements.append(Spacer(1, 140))
elements.append(EnergyLabel(68))

doc.build(elements)