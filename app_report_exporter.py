import decimal
from pydoc import doc
import os
import numpy as np
from sympy import re
import db_api
import statistics
from typing import Iterable, List, Dict, Any, Annotated, Union
from  functools import wraps
import pendulum as pdl
import PIL.Image
import io
import uuid
import models
from flask import abort
from flask_babel import _, lazy_gettext
from typing import Literal
import time
import concurrent.futures as cf

# from app_energy_label import EnergyLabel


# PDF generation imports
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, Image as RLImage, PageBreak, Frame, PageTemplate, ListFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable
from xml.sax.saxutils import escape as xml_escape
from dotenv import load_dotenv

# mask colours must match --mask-bitumen / --mask-aggregate in static/app.css (the app's viewer)
REPORT_COLORS = {
    # "topic_color": "#4ecdc4",      # turquoise
    "topic_color": "#2b2b2b",      # light gray
    "mask_asphalt": "#1f4fff",   # blue
    "mask_aggregate": "#e8323c",      # red
    # "warning_color": "#fff3cd",  # pale orange
    "warning_color": "#ffffff",  # white
    "warning_text_color": "#ff6b6b",   # red 
}

load_dotenv(dotenv_path='.env')
SIMILARITY_THRESHOLD=os.getenv('SIMILARITY_THRESHOLD', 0.9)
SIMILARITY_THRESHOLD=float(SIMILARITY_THRESHOLD)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
        name="Unicode",
        fontName="DejaVu",
        fontSize=11,
        leading=14,
    ))

styles["Title"].fontName = "DejaVu-Bold"
styles["Heading1"].fontName = "DejaVu-Bold"
styles["Heading2"].fontName = "DejaVu-Bold"
styles["Heading3"].fontName = "DejaVu-Bold"
styles["Heading4"].fontName = "DejaVu-Bold"

# styles["Heading1"].fontSize = 16
# styles["Heading2"].fontSize = 14
# styles["Heading3"].fontSize = 12
# styles["Heading4"].fontSize = 11

style_justify = ParagraphStyle(
    name="Justified",
    # parent=styles["Normal"],
    parent=styles["Unicode"],
    alignment=TA_JUSTIFY,
    fontSize=10.5,
    leading=14,
)

style_justify_right = ParagraphStyle(
    name="JustifiedRight",
    parent=style_justify,
    alignment=TA_RIGHT,
)

style_left = ParagraphStyle(
    name="Left",
    parent=style_justify,
    alignment=TA_LEFT,
)

# mask colour legend under the processed image - wraps within the image column (longer in some languages)
style_legend = ParagraphStyle(
    name="Legend",
    parent=style_justify,
    alignment=TA_CENTER,
    fontSize=9,
    leading=11,
)

styles.add(ParagraphStyle(
    name="TableHeader",
    parent=style_justify,
    alignment=TA_CENTER,
    fontName="DejaVu-Bold",
    textColor=colors.white,
    fontSize=10,
))

warning_style = ParagraphStyle(
    name="Warning",
    # fontName="Helvetica-Bold",
    fontName="DejaVu-Bold",
    fontSize=10,
    leading=12,
    alignment=TA_JUSTIFY,
    # textColor=colors.HexColor("#d09200ff"),
    # textColor=colors.HexColor("#d0720062"),
    textColor=colors.HexColor(REPORT_COLORS["warning_text_color"]),
    spaceBefore=6,
    spaceAfter=6,
)

# from app import UserTemporaryStorage
def hex_to_RGB(hex_color: str) -> List[int]:
    hex_color = hex_color.lstrip('#')
    return [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]

exporter_registry: Dict[str, Any] = {}

pdfmetrics.registerFont(
    TTFont('DejaVu', 'DejaVuSans.ttf')
)
pdfmetrics.registerFont(
    TTFont('DejaVu-Bold', 'DejaVuSans-Bold.ttf')
)




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
        c.setFont("DejaVu-Bold", 14)
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
        c.setFont("DejaVu-Bold", 14)
        c.drawString(x + 15, y + height / 2 - 6, text)

    def draw_left_box(self, c):
        box_width = 130
        box_height = (self.bar_height+self.spacing)*len(self.classes)-self.spacing

        c.setFillColor(colors.white)
        c.setStrokeColor(colors.black)
        c.rect(0, self.height - box_height, box_width, box_height, fill=1)

        c.setFillColor(colors.black)
        c.setFont("DejaVu", 12)
        c.drawCentredString(box_width / 2,
                            self.height - box_height * 1.25 / 5,
                            _("Adhesion")
        )
        c.setFont("DejaVu-Bold", 18)
        c.drawCentredString(box_width / 2,
                            self.height - box_height * 2 / 5,
                            f"{self.adhesion_rate:.0f} %")

        c.setFont("DejaVu", 12)
        c.drawCentredString(box_width / 2,
                            self.height - box_height * 3.25 / 5,
                            _("Rating"))
        c.setFont("DejaVu-Bold", 14)
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



def experiment_masks(experiment: Dict[str, Any], experiment_id: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Asphalt and aggregate masks of a sample as evaluated in the app (stored masks + manual corrections).
    The model only runs for samples without stored masks; its result is stored for the next export.
    """
    def corrected(mask_key: str, corrections_key: str):
        mask = memory_to_np_array(experiment[mask_key])
        corrections = experiment.get(corrections_key)
        if corrections is not None:
            mask = np.clip(mask + memory_to_np_array(corrections), 0, 1)
        return mask.astype(bool)

    if experiment.get("asphalt_mask") is not None and experiment.get("aggregate_mask") is not None:
        asphalt_mask = corrected("asphalt_mask", "asphalt_mask_manual_corrections")
        aggregate_mask = corrected("aggregate_mask", "aggregate_mask_manual_corrections")
        if asphalt_mask.any() or aggregate_mask.any():  # all-zero masks = the model never ran for this sample
            return asphalt_mask, aggregate_mask

    model = experiment.get("inference_model")
    if model in models.discover_models():
        model_name = model
    elif model in models.discover_models(deprecated=True):
        model_name = os.path.join("deprecated", model)
    else:
        abort(500, description=_("Inference model ") + str(model) + _(' not available for experiment ID') + str(experiment_id) + '. ' + _("Please use newer model for this specimen or contact us to resolve this issue."))
    asphalt_mask, aggregate_mask, background_mask = models.inference_on_numpy(
        np_image=memory_to_np_array(experiment.get("color")), model_name=model_name)
    db_api.update_experiment_in_db(values_dict={
        "asphalt_mask": to_byetarray(asphalt_mask.astype(np.uint8)),
        "aggregate_mask": to_byetarray(aggregate_mask.astype(np.uint8)),
    }, experiment_id=experiment_id)
    return asphalt_mask.astype(bool), aggregate_mask.astype(bool)

def to_byetarray(np_array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, np_array)
    return buffer.getvalue()

def process_image(original_image: np.ndarray, mask_asphalt: np.ndarray, mask_aggregate: np.ndarray) -> np.ndarray:
    """
    Create a processed image highlighting asphalt and aggregate areas.

    Args:
        original_image (np.ndarray): The original image as a NumPy array.
        mask_asphalt (np.ndarray): Binary mask for asphalt areas.
        mask_aggregate (np.ndarray): Binary mask for aggregate areas.

    Returns:
        np.ndarray: The processed image with highlighted areas.
    """
    # Create an empty image with the same shape as the original
    processed_img = original_image.copy()

    # Highlight asphalt areas in blue
    color_rgb = hex_to_RGB(REPORT_COLORS["mask_asphalt"])
    processed_img[mask_asphalt == 1] = color_rgb  # Blue color for asphalt

    # Highlight aggregate areas in red
    color_rgb_aggregate = hex_to_RGB(REPORT_COLORS["mask_aggregate"])
    processed_img[mask_aggregate == 1] = color_rgb_aggregate  # Red color for aggregate

    return processed_img

def register_exporter(name: str):
    def decorator(cls):
        exporter_registry[name] = cls
        return cls
    return decorator

def esc(value, default: str = '-') -> str:
    """Text for reportlab Paragraph markup - user data must not be parsed as markup (e.g. '<frakce 8/16>' or '<img>')."""
    if value is None or value == '' or value == 'None':
        return default
    return xml_escape(str(value))

def as_float(value) -> float | None:
    """Number from a DB value; None for missing or unreadable values (which are left out of the statistics)."""
    try:
        return None if value is None or value in ('', '-', 'None') else float(value)
    except (TypeError, ValueError):
        return None

def percent(value) -> str:
    number = as_float(value)
    return f"{100 * number:.2f}" if number is not None else '-'

def memory_to_np_array(memory: bytes) -> np.ndarray:
    buffer = io.BytesIO(bytes(memory))
    array = np.load(buffer, allow_pickle=True)  
    # array = np.load(buffer)  
    return array


def get_CSN_73_6161_word_classification(adhesion_rate: float) -> str:
    if adhesion_rate >= 97.0:
        return _("Excellent")
    elif adhesion_rate >= 90.0:
        return _("Good")
    elif adhesion_rate >= 80.0:
        return _("Satisfactory")
    else:
        return _("Unsatisfactory")

def get_CSN_73_6161_classification(adhesion_rate: float) -> str:
    if adhesion_rate >= 100.0:
        return "A"
    elif adhesion_rate >= 90.0:
        return "B"
    elif adhesion_rate >= 80.0:
        return "C"
    elif adhesion_rate >= 70.0:
        return "D"
    elif adhesion_rate >= 50.0:
        return "E"
    elif adhesion_rate >= 40.0:
        return "F"
    elif adhesion_rate >= 20.0:
        return "G"
    else:
        return _("Unclassifiable")

# Compute the asphalt adhesion statistics
def compute_statistics(assessments: List[float], to_per_cents: bool = True) -> Dict[str, Union[float, str]]:
    assessments = [float(a) for a in assessments if a is not None]
    if not assessments:
        # e.g. no selected sample has an expert guess yet
        return {"average": None, "stddev": None, "worst": None,
                "average_classification": "-", "average_word_classification": "-", "worst_classification": "-"}
    average = float(np.mean(assessments))
    worst = float(np.min(assessments))
    stddev = float(np.std(assessments) if len(assessments) > 1 else 0.0)
    
    if to_per_cents:
        average *= 100.0
        worst *= 100.0
        stddev *= 100.0

    return {
        "average": average,
        "stddev": stddev,
        "worst": worst,
        "average_classification": get_CSN_73_6161_classification(average),
        "average_word_classification": get_CSN_73_6161_word_classification(average),
        "worst_classification": get_CSN_73_6161_classification(worst),
    }


###### 
###### 
###### MAIN EXPORTER
###### 
###### 

@register_exporter("CSN_73_6161")
def csn_73_6161_exporter(experiment_ids: Iterable[int], report_id: str, user_id: int, controlling_user_id: int = None, ordering_party: Dict[str, Any] = {}, controlling_employee: Dict[str, Any] = {}, as_buffer=True) -> io.BytesIO | None:
    """
    Exports the experiment report data with fields required by CSN 73 6161 standard.

    Args:
        experiment_ids (Iterable[int]): List of experiment IDs to export data for.
        ordering_party (Dict[str, Any], optional): Information about the ordering party. Defaults to {}.
        controlling_employee (Dict[str, Any], optional): Information about the controlling employee. Defaults to {}.
    Returns:
        None
    """
    # Fetch experiment data from the database
    user_info = db_api.get_user_by_id(user_id)
    company_id = user_info.get("company", None)
    company_info = db_api.get_company_info_by_id(company_id)
    laboratory_info = {
        "name": company_info.get("company_name", "-"),
        "address": company_info.get("company_address", "-"),
        "contact": company_info.get("e_mail", "-"),
    }

    report_date = pdl.now()
    
        # pdf.append(line)
    # Prepare PDF content
    # as_buffer = False # for testing purposes
    metadata = {
        "title": _("AIBAL Report"),
        "author": user_info.get("first_name", "-") + " " + user_info.get("last_name", "-"),
        "subject": _("AIBAL Report ID:") + f" {report_id}",
        "keywords": _("bitumen, adhesion, test, CSN 73 6161"),
        "application": "AIBAL - AI Bitumen Adhesion Lab",
    }
    if as_buffer:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=30*mm, bottomMargin=25*mm, **metadata)
    else:
        doc = SimpleDocTemplate(f"test_report.pdf", pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=30*mm, bottomMargin=25*mm, **metadata)
    pdf = []

    # REUSE THE SAME SEPARATOR THROUGHOUT THE DOCUMENT
    separator = Drawing(doc.width ,1 * mm)
    separator.add(Rect(0, 0, doc.width, 1 * mm, fillColor=colors.HexColor(REPORT_COLORS["topic_color"]), strokeWidth=0, strokeColor=colors.HexColor(REPORT_COLORS["topic_color"])))



    # pdf.append(Spacer(0,20))


    # Title
    # pdf.append(PageBreak())
    pdf.append(Spacer(1, 0.2 * cm))
    pdf.append(Paragraph(_("Bitumen Adhesion Test Protocol"), styles["Title"]))
    pdf.append(Spacer(1, 0.3 * cm))

    n_samples = len(experiment_ids)
    text = _("""
    This report provides a comprehensive overview of the bitumen adhesion test protocol,
    with all relevant information according to the CSN 73 6161 standard.
    The adhesion test was performed on """) + f"{n_samples}" + _(""" samples of asphalt mixtures. The detailes about each specimen included below, the overview is at the end of the document.""")
    pdf.append(Paragraph(text, style_justify))
    pdf.append(Spacer(1, 0.3 * cm))

    text = _("""
    Both the visual expert assesment and the AI-based quantitative analysis are included in this report.
    If this two contradict each other, the visual expert assesment is considered the final result, however,
    the AI-based visualization is included for reference. 
    """)

    pdf.append(Paragraph(text, style_justify))
    pdf.append(Spacer(1, 0.2 * cm))
    
    energy_label_position = len(pdf)


    op = {
        "Caption": _("Ordering Party"),
    }
    op.update(ordering_party)
    dat1 = party_details_data(pdf, op)

    li = { 
        "Caption": _("Providing Laboratory"),
    }
    li.update(laboratory_info)
    dat2 = party_details_data(pdf, li)

    list_ = ["", ""]
    pdf.append(Spacer(0,25))
    list_.append([dat1, dat2])
    pdf = two_col_text_layout(pdf, list_, doc=doc)

    left_column = [
        Paragraph(_("The proceeding employee"), styles["Heading2"]),
        Paragraph(_("Name:") + f" {esc(user_info.get('first_name'))} {esc(user_info.get('last_name'), '')}", style_justify),
        Paragraph(_("Contact:") + f" {esc(user_info.get('e_mail'))}", style_justify),
        Spacer(1, 1.0 * cm),
        Paragraph(_("Signature: ..................................................."), style_justify),
        Spacer(1, 0.3 * cm),
    ]

    # Responsible Employees
    controlling_employee = user_info
    if controlling_user_id:
        try:
            controlling_employee = db_api.get_user_info_by_id(controlling_user_id)
        except Exception:
            controlling_employee = user_info

    right_column = [
        # Paragraph(_("The controlling employee"), styles["Heading2"]),
        Paragraph(_("The controll performed by"), styles["Heading2"]),
        Paragraph(_("Name:") + f" {esc(controlling_employee.get('first_name'))} {esc(controlling_employee.get('last_name'), '')}", style_justify),
        Paragraph(_("Contact:") + f" {esc(controlling_employee.get('e_mail'))}", style_justify),
        Spacer(1, 1.0 * cm),
        Paragraph(_("Signature: ..................................................."), style_justify),
        Spacer(1, 0.3 * cm),
    ]

    table_data = ["", ""]
    table_data.append([left_column, right_column])
    pdf.append(Spacer(0,25))
    pdf = two_col_text_layout(pdf, table_data, doc=doc)
    pdf.append(PageBreak())





    # Insert experiment records
    assessments_expert_guess = []
    assessments_automatic = []
    concerns = {"similar_images": 0, "old_images": 0}
    experiments = {id: db_api.get_experiment_by_id(id) for id in experiment_ids}
    timesteps = {id: db_api.get_experiment_timestamp_by_id(id) for id in experiment_ids}
    # def process_single_image(experiment, eid):
        
    for experiment, experiment_id, timestep in zip(experiments.values(), experiment_ids, timesteps.values()):
        experiment.update({"timestamp": timestep})
        original_image = memory_to_np_array(experiment.get("color"))
        # the masks as evaluated in the app (the model only runs for samples without stored masks)
        asphalt_mask, aggregate_mask = experiment_masks(experiment, experiment_id)
        if as_float(experiment.get("asphalt_ratio")) is None:
            # never evaluated - compute the coverage from the masks instead of failing on a missing value
            covered = int(asphalt_mask.sum())
            total = covered + int(aggregate_mask.sum())
            experiment["asphalt_ratio"] = covered / total if total else None

        similar_dict = get_similar_experiment(experiment)
        # Add experiment record to PDF
        pdf.append(Spacer(1, 0.4 * cm))
        pdf.append(separator)
        pdf.append(Spacer(1, 0.2 * cm))
        pdf = add_experiment_record(pdf, experiment, similar=similar_dict, doc=doc)

        processed_image = process_image(
            original_image,
            asphalt_mask,
            aggregate_mask
        )
        pdf = add_images(
            pdf, 
            # img_original=memory_to_np_array(experiment.get("color")), 
            img_original=original_image, 
            img_processed=processed_image,
            similar_image=similar_dict if similar_dict else {},
            max_image_size_cm=[doc.width/2, doc.width/2],
            doc=doc
        )

        # Collect assessments - missing values are left out of the statistics (they used to count as 0 %)
        assessments_expert_guess.append(as_float(experiment.get("expert_guess")))
        assessments_automatic.append(as_float(experiment.get("asphalt_ratio")))

        # Count suspicious cases
        if similar_dict:
            concerns["similar_images"] += 1

        experiment_date_str = str(experiment.get("timestamp", ''))
        experiment_date = pdl.parse(experiment_date_str) 
        if (report_date - experiment_date).days > 180:
            concerns["old_images"] += 1



    # Compute statistics
    stats_expert = compute_statistics(assessments_expert_guess)
    stats_automatic = compute_statistics(assessments_automatic)

    labels = []
    for title, stats in ((_("Resulting assesment - expert"), stats_expert), (_("Resulting assesment - automatic"), stats_automatic)):
        labels.append(Paragraph(title, styles["Heading2"]))
        labels.append(EnergyLabel(stats["average"]) if stats["average"] is not None else Paragraph("-", style_justify))
        labels.append(Spacer(1, 0.2 * cm))
    pdf[energy_label_position:energy_label_position] = labels

    # pdf.insert(energy_label_position-1,Spacer(0,20))


    # PRINT FINAL SUMMARY
    # Final - table
    pdf.append(PageBreak())
    pdf.append(Paragraph(_("Tabular overview"), styles["Heading2"]))
    table_data = [[
        Paragraph(_("Specimen ID"), styles["TableHeader"]),
        Paragraph(_("Visual Expert Assessment [%]"), styles["TableHeader"]), 
        Paragraph(_("AI-based Assesment  [%]"), styles["TableHeader"])
    ]]


    # specimen ID together with the user's designation of the sample (if any)
    specimens = []
    for eid, exp in zip(experiment_ids, experiments.values()):
        label = exp.get('info_sample_label')
        specimens.append(Paragraph(xml_escape(f"{eid} – {label}" if label not in (None, '', '-') else str(eid)), style_left))

    table_data.extend(
        [ items for items in zip(
            specimens,
            [percent(exp.get('expert_guess')) for exp in experiments.values()],
            [percent(exp.get('asphalt_ratio')) for exp in experiments.values()],
        )]
    )
    pdf = add_table(pdf, table_data, colWidths=[doc.width/3]*3)
    pdf.append(Spacer(1, 1.0 * cm))

    # Final summary + issues
    pdf.append(Paragraph(_("Report Conclusion"), styles["Heading2"]))
    # pdf.append(Paragraph(_("Summary"), styles["Heading3"]))
    items = []
    if stats_expert['average'] is not None:
        items.append(Paragraph(_("The average adhesion rate across all samples is") + f" {stats_expert['average']:.2f} ± {stats_expert['stddev']:.2f} % " + _("according to expert visual assesment, which correspondes to calss") + f" {stats_expert['average_classification']}. ", style_justify))
    if stats_automatic['average'] is not None:
        items.append(Paragraph(_("The average adhesion rate across all samples is") + f" {stats_automatic['average']:.2f} ± {stats_automatic['stddev']:.2f} % " + _("according to AI-based analysis, which correspondes to calss") + f" {stats_automatic['average_classification']}. ", style_justify))
    if stats_expert['worst'] is not None:
        items.append(Paragraph(_("The worst adhesion rate (") +f"{stats_expert['worst']:.2f}" + _(" %) observed is class ") + f"{stats_expert['worst_classification']} " + _("according to expert visual assesment."), style_justify))
    if stats_automatic['worst'] is not None:
        items.append(Paragraph(_("The worst adhesion rate (") +f"{stats_automatic['worst']:.2f}" + _(" %) observed is class ") + f"{stats_automatic['worst_classification']} " + _("according to AI-based analysis."), style_justify))
    pdf = add_itemized_list(pdf, items)
    pdf.append(Paragraph(_("The final considered class is: ") + f"{stats_expert['average_classification']}", styles["Heading4"]))
    pdf.append(Paragraph(_("The adhesion between aggregate and binder is classified as: ") + f"{stats_expert['average_word_classification']}", styles["Heading4"]))
    
    issues = []
    if concerns["similar_images"] > 0:
        issues.append(f"{concerns['similar_images']}/{len(experiment_ids)}" + _(" images seem to highly similar with others and might not be unique specimens."))
    if concerns["old_images"] > 0:
        issues.append(f"{concerns['old_images']}/{len(experiment_ids)}" + _(" have been uploaded more than 6 months ago."))
    if len(experiment_ids) < 2:
        issues.append(_("The report contains less than 2 samples, which is insufficient for CSN 73 6161 standard compliance."))
    expert_values = [a for a in assessments_expert_guess if a is not None]
    automatic_values = [a for a in assessments_automatic if a is not None]
    if expert_values and max(expert_values) - min(expert_values) > 0.1:
        issues.append(_("Significant variance detected between expert assessments (>10%) of different samples. The CSN 73 6161 standard requires experiment repetition."))
    if automatic_values and max(automatic_values) - min(automatic_values) > 0.1:
        issues.append(_("Significant variance detected between AI-based assessments (>10%) of different samples. The CSN 73 6161 standard requires experiment repetition. Consider this in case that the AI based results seem reliable."))
    if len(issues) > 0:
        pdf.append(Paragraph(_("Concerns"), styles["Heading2"]))
        items = [Paragraph(issue, style_justify) for issue in issues]
        pdf = add_itemized_list(pdf, items)
        pdf.append(Spacer(1, 1.0 * cm))
    
    # Responsible Employees
    controlling_employee = user_info
    if controlling_user_id:
        try:
            controlling_employee = db_api.get_user_info_by_id(controlling_user_id)
        except Exception:
            controlling_employee = user_info
    

    pdf.append(Spacer(1, 1.0 * cm))
    pdf.append(Paragraph(_("This report was generated using AIBAL on ") + f"{report_date.to_datetime_string()}.", style_justify_right))
    
    
    doc.build(pdf,
        # onFirstPage=lambda canvas, doc: first_page(canvas, doc, report_id=report_id),
        onFirstPage=lambda canvas, doc: styled_header_footer(canvas, doc, report_id=report_id),
        onLaterPages=lambda canvas, doc: styled_header_footer(canvas, doc, report_id=report_id)
    )
    
    if as_buffer:
        return buffer.getvalue()
    else:
        return None


def get_similar_experiment(experiment: Dict[str, Any], threshold: float = SIMILARITY_THRESHOLD) -> Dict[str, Any]:  
    similar_ssim_id = experiment.get("similar_ssim_id", None)
    similar_ssim_value = experiment.get("similar_ssim_value", 0.0)
    similar_hist_id = experiment.get("similar_hist_id", None)
    similar_hist_value = experiment.get("similar_hist_value", 0.0)
    
    similar_hist_value = 0.0 if similar_hist_value is None else similar_hist_value
    similar_ssim_value = 0.0 if similar_ssim_value is None else similar_ssim_value

    similar_dict = {}
    if all(v < threshold for v in [similar_hist_value, similar_ssim_value]):
        return similar_dict
    
    if any(v is not None for v in [similar_ssim_id, similar_hist_id]):
        # assume the higher value indicates more similarity
        similar_dict.update({"similar_experiment_id": similar_hist_id, "similarity_score": similar_hist_value, "similarity_method": "Histogram Comparison"})
        if similar_ssim_value >= similar_hist_value:
            similar_dict.update({"similar_experiment_id": similar_ssim_id, "similarity_score": similar_ssim_value, "similarity_method": "SSIM"})

        similar_experiment = db_api.get_experiment_by_id(similar_dict.get("similar_experiment_id"))
        similar_user_id = similar_experiment.get("user_id", None)
        similar_dict["similar_user_e_mail"] =  db_api.get_user_info_by_id(similar_user_id).get("e_mail", None)
        similar_dict["similar_upload_date"] =  db_api.get_experiment_timestamp_by_id(similar_dict.get("similar_experiment_id"))
        similar_dict["similar_upload_date"] =  pdl.parse(str(similar_dict["similar_upload_date"])).to_datetime_string()

        # Get similar image
        similar_dict["similar_image"] = memory_to_np_array(similar_experiment.get("color"))

    return similar_dict    
    
def add_table(pdf: list, table_data: List[List[Any]], colWidths: List[float] = None) -> list:
    """
    Add a table to the PDF.
    
    Args:
        pdf (list): The PDF content list to append to.
        table_data (List[List[Any]]): The table data as a list of rows.
        col_widths (List[float], optional): Column widths in cm. Defaults to None.

    Returns:
        pdf (list): The updated PDF content list.
    """

    # if col_widths:
    #     col_widths_cm = [w * cm for w in col_widths]
    # else:
    #     col_widths_cm = None

    table = Table(table_data, colWidths=colWidths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), REPORT_COLORS["topic_color"]),
        # Header text color → white
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0, colors.white),
        ("FONT", (0, 0), (-1, -1), "DejaVu"),
        ("FONT", (0, 0), (-1, 0), "DejaVu-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "TOP"),
    ]))

    pdf.append(Spacer(1, 0.2 * cm))
    pdf.append(table)
    return pdf

def return_similarity_warning(pdf: list, similar_dict: dict) -> list:
    """
    Add a similarity warning to the PDF if the similarity score exceeds the threshold.
    
    Args:
        pdf (list): The PDF content list to append to.
        similarity_score (float): The similarity score between two samples.
        threshold (float): The threshold above which to show the warning.

    Returns:
        pdf (list): The updated PDF content list.
    """

    experiment_id = similar_dict.get("experiment_id")
    similar_experiment_id = similar_dict.get("similar_experiment_id")
    similar_user_e_mail = similar_dict.get("similar_user_e_mail")
    similarity_score = similar_dict.get("similarity_score")
    similarity_method = similar_dict.get("similarity_method")
    similar_date = similar_dict.get("similar_upload_date")

    warning_text = _("<<< ⚠ WARNING: The program has detected a highly similar image (on the left, experiment_id:") + \
        f"{esc(similar_experiment_id)}" + _(" , uploaded by ") + f"{esc(similar_user_e_mail)}" + _(" on ") + f"{esc(similar_date)}" + \
        _(") with") + f" {100*similarity_score:.2f}% " + _("confidence. ") + \
        _("""Please review the samples for potential duplication. In case the specimens clearly aren't duplicates, you can ignore this message.""")
        # _("using") + f" {similarity_method}. " + \
    warning_para = Paragraph(warning_text, warning_style)

    warning_box = Table(
        [[warning_para]],
        colWidths=[None]  # auto-fit to page width
    )

    warning_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), REPORT_COLORS["warning_color"]),  # pale orange
        # ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#ffcc80")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return warning_box


def add_images(pdf: list, img_original: PIL.Image,  img_processed: PIL.Image, similar_image: dict = None,max_image_size_cm: list = [8, 8], doc=None) -> list:
    """
    Add two images (original and processed) to the PDF, next to each other.
    Args:
        pdf (list): The PDF content list to append to.
        img_original (PIL.Image): The original image.
        img_processed (PIL.Image): The processed image.
        max_image_size_cm (list): Maximum size for each image in cm [width, height].
    Returns:
        pdf (list): The updated PDF content list.
    """
    table_data = []
    img1 = get_printable_image(img_original, max_image_size_cm)
    img2 = get_printable_image(img_processed, max_image_size_cm)
    table_data.append([_("Original Image"), _("Processed Image")])
    table_data.append([img1, img2])
    # non-breaking spaces around the dashes: a line may break only between the "material - colour" pairs
    legend = _("(Bitumen - blue, aggregate - red)").replace(" – ", " – ").replace(" - ", " - ")
    table_data.append(["", Paragraph(xml_escape(legend), style_legend)])
    if similar_image:
        warning_box = return_similarity_warning(pdf, similar_image)
        similar_image_printable = get_printable_image(similar_image.get("similar_image"), max_image_size_cm)
        table_data.append([similar_image_printable, warning_box])
        # pdf.append(Spacer(1, 0.2 * cm))
    # pdf = add_table(pdf, table_data, col_widths=[max_image_size_cm[0], max_image_size_cm[0]])
    pdf = add_table(pdf, table_data, colWidths=[doc.width/2.0]*2)
    return pdf   

def get_resized_dimensions(img: PIL.Image.Image, max_image_size_cm: list) -> tuple:
    if isinstance(img, np.ndarray):
        img = PIL.Image.fromarray(img)
    max_size_id = np.argmax(img.size)
    img_width, img_height = img.size

    # Rotate if portrait to landscape, to save space
    if img_height > img_width:
        img = img.rotate(90, expand=True)
        img_width, img_height = img.size

    aspect_ratio = img_width / img_height

    if max_size_id == 0:  # width is the limiting factor
        img_width = max_image_size_cm[0]
        img_height = img_width / aspect_ratio
        if img_height > max_image_size_cm[1]:
            img_height = max_image_size_cm[1]
            img_width = img_height * aspect_ratio
    else:  # height is the limiting factor
        img_height = max_image_size_cm[1]
        img_width = img_height * aspect_ratio
        if img_width > max_image_size_cm[0]:
            img_width = max_image_size_cm[0]
            img_height = img_width / aspect_ratio

    return img, img_width, img_height    

def get_printable_image(img: PIL.Image.Image | np.ndarray, max_image_size_cm: list = [9, 9]) -> RLImage:
    img, img_width, img_height = get_resized_dimensions(img, max_image_size_cm)
    if isinstance(img, np.ndarray):
        img = PIL.Image.fromarray(img)
    buf = io.BytesIO()
    # img.save(buf, format="PNG")
    img.save(buf, format="JPEG", quality=50, optimize=True)
    buf.seek(0)
    rlimg = RLImage(buf, width=img_width, height=img_height)
    return rlimg

def add_image(pdf: list, img: PIL.Image.Image | np.ndarray, max_image_size_cm: list = [9, 9]) -> list:
    # Resize image while maintaining aspect ratio
    pdf.append(Spacer(1, 0.2 * cm))
    rlimg = get_printable_image(img, max_image_size_cm)
    pdf.append(rlimg)
    return pdf

def add_experiment_record(pdf: list, experiment: Dict[str, Any], similar: dict = None, doc: Any = None) -> list:
    """
    Add experiment record to the PDF.
    
    Args:
        pdf (list): The PDF content list to append to.
        experiment (Dict[str, Any]): The experiment data.
        - keys: 'id', 'date', ''
    Returns:
        pdf (list): The updated PDF content list.
    """

    # missing values are printed as '-' (without changing the caller's data, which the statistics use)
    left_column = [
        Paragraph(_("Sample ID:") + f" {esc(experiment.get('experiment_id'))}", styles["Heading3"]),
        Paragraph(_("Sample Designation:") + f" {esc(experiment.get('info_sample_label'))}", style_left),
        Paragraph(_("Date:") + f" {esc(experiment.get('info_datetime'))}", style_justify),
        Paragraph(_("Place of Experiment:") + f" {esc(experiment.get('info_place_of_experiment'))}", style_justify),
        Paragraph(_("Sample Collection Data:") + f" {esc(experiment.get('info_sample_collection_data'))}", style_justify),
        Paragraph(_("Aggregate:") + f" {esc(experiment.get('info_aggregate'))}", style_justify),
        Paragraph(_("Binder:") + f" {esc(experiment.get('info_binder'))}", style_justify),
        Paragraph(_("Wrapping temperature aggregate [°C]:") + f" {esc(experiment.get('info_wrapping_temperature_aggregate'))}", style_justify),
        Paragraph(_("Wrapping temperature binder [°C]:") + f" {esc(experiment.get('info_wrapping_temperature_binder'))}", style_justify),
        Paragraph(_("Exposing water temperature [°C]:") + f" {esc(experiment.get('info_exposing_water_temperature'))}", style_justify),
        Paragraph(_("Test procedure:") + f" {esc(experiment.get('info_test_procedure'))}", style_justify),
    ]

    right_column = [
        Paragraph(_("Assessment - Adhesion Rate:"), styles["Heading4"]),
        Paragraph(_("Inference Model:") + f" {esc(experiment.get('inference_model'))}", style_justify),
        Paragraph(_("Automatic Assessment [%]:") + f" {percent(experiment.get('asphalt_ratio'))}", style_justify),
        Paragraph(_("Visual based Expert Guess [%]:") + f" {percent(experiment.get('expert_guess'))}", style_justify),
        Paragraph(_("Comment:") + f" {esc(experiment.get('info_comment'))}", style_justify),
    ]
    table_data = [["", ""]]
    table_data.append([left_column, right_column])
    pdf = two_col_text_layout(pdf, table_data, doc=doc)
    pdf.append(Spacer(1, 0.2 * cm))
    return pdf    

def first_page(canvas, doc, report_id: str):
    styled_header_footer(canvas, doc, report_id)
    canvas.saveState()

    width, height = doc.pagesize

    # Draw company logo (top-left)
    logo = PIL.Image.open("static/logo-text.png")
    logow, logoh = logo.size
    logo_scale = 80 * mm / logow

    # x position to center the image
    # x = (width - logo_scale * logow) / 4
    x = doc.leftMargin

    # y position (from bottom) — here we keep your previous top margin calculation
    y = height - 70 * mm  # adjust as needed


    canvas.drawImage(
        "static/logo-text.png",
        x,
        y,
        width=logo_scale * logow,
        height=logo_scale * logoh,
        mask="auto"
    )
    # # Draw company logo (top-left)
    # logo = PIL.Image.open("static/logo-text.png")
    # logow, logoh = logo.size
    # logo_scale = 30 * mm / logow

    # # x position to center the image
    # x = (width - logo_scale * logow) / 2

    # # y position (from bottom) — here we keep your previous top margin calculation
    # y = height - 110 * mm  # adjust as needed


    # canvas.drawImage(
    #     "static/logo-text.png",
    #     x,
    #     y,
    #     width=logo_scale * logow,
    #     height=logo_scale * logoh,
    #     mask="auto"
    # )
    

    # # canvas.setFillColor(colors.HexColor(REPORT_COLORS["topic_color"]))
    # # rect_width = 210 * mm
    # # rect_height = 120 * mm
    # # rect_x = (width - rect_width) / 2 
    # # rect_y = height - 200 * mm - rect_height / 2
    # canvas.setStrokeColor(colors.black)
    # canvas.setStrokeAlpha(0)
    # canvas.rect(rect_x, rect_y, rect_width, rect_height, fill=1)



    # -------------------
    # Draw some text
    # -------------------
    # canvas.setFont("DejaVu-Bold", 14)
    # # canvas.setFont("DejaVu-Bold", 14)
    # canvas.setFillColor(colors.black)
    # # canvas.drawString(50*mm, height - 70*mm, "Hello, ReportLab Drawing!")


    # # Draw report title (centered)
    canvas.restoreState()
    canvas.setFillColor(colors.black)
    canvas.setFont("DejaVu-Bold", 36)
    canvas.drawCentredString(
        width / 2,
        height - 200 * mm,
        _("AIBAL Report"),    )
    canvas.saveState()
    PageBreak()

def styled_header_footer(canvas, doc, report_id: str):
    canvas.saveState()

    width, height = doc.pagesize

    header_height = 26 * mm
    footer_height = 15 * mm

    # ======================
    # Header background bar
    # ======================
    canvas.setFillColor(colors.HexColor(REPORT_COLORS["topic_color"]))
    canvas.rect(
        0,
        height - header_height,
        width,
        header_height,
        fill=1,
        stroke=0
    )
    # canvas.rect(
    #     0,
    #     height - header_height,
    #     doc.leftMargin,
    #     header_height,
    #     fill=1,
    #     stroke=0
    # )
    # canvas.rect(
    #     doc.leftMargin + 45* mm, 
    #     height - header_height,
    #     width,
    #     header_height,
    #     fill=1,
    #     stroke=0
    # )

    # Draw company logo (top-left)
    # logo = PIL.Image.open("static/logo-text.png")
    logo = PIL.Image.open("static/logo_white.png")
    logow, logoh = logo.size
    logo_scale = 40 * mm / logow

    # x position to center the image
    # x = (width - logo_scale * logow) 
    x = doc.leftMargin + 2 * mm
    # x = 16 * mm

    # y position (from bottom) — here we keep your previous top margin calculation
    y = height - 23 * mm  

    canvas.drawImage(
        "static/logo_white.png",
        x,
        y,
        width=logo_scale * logow,
        height=logo_scale * logoh,
        mask="auto"
    )

    # Header bottom line
    # canvas.setStrokeColor(colors.black)
    color=REPORT_COLORS["topic_color"]
    canvas.setStrokeColor(color)
    canvas.setLineWidth(1)
    # canvas.line(
    #     # 65 * mm,
    #     # doc.leftMargin,
    #     0,
    #     height - header_height,
    #     width - doc.rightMargin,
    #     height - header_height
    # )

    # Header text
    canvas.setFillColor(colors.white)
    # color = REPORT_COLORS["mask_aggregate"]
    # canvas.setFillColor(color)
    canvas.setFont("DejaVu-Bold", 13)
    canvas.drawString(
        doc.leftMargin + 132 *mm,
        # width-doc.rightMargin,
        height - header_height +  8* mm,
        _("AIBAL Report")
    )
    # canvas.setFont("DejaVu-Bold", 10)
    # canvas.drawString(
    #     doc.leftMargin + 132 *mm,
    #     # width-doc.rightMargin,
    #     height - header_height + 1 * mm,
    #     f"ID: {report_id}" 
    # )

    # ======================
    # Footer separator line
    # ======================
    canvas.setStrokeColor(colors.grey)
    canvas.setLineWidth(0.5)
    canvas.line(
        doc.leftMargin,
        # 80 * mm,
        footer_height,
        width - doc.rightMargin,
        footer_height
    )

    # Footer text
    canvas.setFillColor(colors.grey)
    canvas.setFont("DejaVu", 9)
    canvas.drawString(
        doc.leftMargin,
        footer_height - 6 * mm,
        _("Report generated by AIBAL -Bitumen Adhesion Lab - report ID:") + f" {report_id}"  # Assuming report_id is defined elsewhere
    )

    # Page number (right aligned)
    canvas.drawRightString(
        width - doc.rightMargin,
        footer_height - 6 * mm,
        _("Page") + f" {doc.page}"
    )

    canvas.restoreState()

def two_col_text_layout(pdf: list, table_data: List[List[str]], doc) -> list:
    """
    Arrange text content in a two-column layout using a table.
    Args:
        pdf (list): The PDF content list to append to.
        table_data (List[List[str]]): The table data as a list of rows. First column is left, second column is right.First row should be empty of empty strings.
    Returns:
        pdf (list): The updated PDF content list.
    """

    table = Table(table_data, colWidths=[doc.width/2.0]*2)
    table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('INNERGRID', (0,0), (-1,-1), 0, colors.white),
        ('BOX', (0,0), (-1,-1), 0, colors.white),
        ('FONT', (0, 0), (-1, -1), "DejaVu"),
        ("LEFTPADDING", (1, 1), (1, 1), 0),
        ("RIGHTPADDING", (1, 1), (1, 1), 0),
        ("VALIGN", (0, 0), (-1, 0), "TOP"),
    ]))

    table._argH[0] = 0 # first row height to 0
    pdf.append(table)
    
    return pdf

def party_details_data(pdf: list, party_info: Dict[str, Any]) -> list:
    data = [
        Paragraph(esc(party_info.get('Caption', 'Party Details')), styles["Heading2"]),
        Paragraph(_("Name:") + f" {esc(party_info.get('name'))}", style_justify),
        Paragraph(_("Address:") + f" {esc(party_info.get('address'))}", style_justify),
        Paragraph(_("Contact:") + f" {esc(party_info.get('contact'))}", style_justify),
        Spacer(1, 0.2 * cm)
    ]

    return data

def add_itemized_list(pdf: list, items: List[Paragraph]) -> list:
    itemized_list = ListFlowable(
        items,
        bulletType="bullet",      # or "1", "a", "A"
        leftIndent=6 * mm,
        # bulletFontName="Helvetica",
        bulletFontName="DejaVu",
        bulletFontSize=10,
    )
    pdf.append(itemized_list)
    return pdf