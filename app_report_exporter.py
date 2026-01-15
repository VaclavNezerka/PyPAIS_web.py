from pydoc import doc
import numpy as np
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

# PDF generation imports
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, Image as RLImage, PageBreak, Frame, PageTemplate, ListFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

REPORT_COLORS = {
    # "topic_color": "#4ecdc4",      # turquoise
    "topic_color": "#2b2b2b",      # light gray
    "mask_asphalt": "#ff6b6b",   # red
    # "mask_aggregate": "#1f4fd8",   # blue
    "mask_aggregate": "#4ecdc4",      # turquoise
    # "warning_color": "#fff3cd",  # pale orange
    "warning_color": "#ffffff",  # white
    "warning_text_color": "#ff6b6b",   # red 
}

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

    # Highlight asphalt areas in red
    color_rgb = hex_to_RGB(REPORT_COLORS["mask_asphalt"])
    processed_img[mask_asphalt == 1] = color_rgb  # Red color for asphalt

    # Highlight aggregate areas in blue
    color_rgb_aggregate = hex_to_RGB(REPORT_COLORS["mask_aggregate"])
    processed_img[mask_aggregate == 1] = color_rgb_aggregate  # Blue color for aggregate

    return processed_img

def register_exporter(name: str):
    def decorator(cls):
        exporter_registry[name] = cls
        return cls
    return decorator

def memory_to_np_array(memory: bytes) -> np.ndarray:
    buffer = io.BytesIO(memory)
    print("Loading array from memory buffer of size:", len(memory))
    array = np.load(buffer, allow_pickle=True)  
    return array


def get_CSN_73_6161_classification(adhesion_rate: float) -> str:
    if adhesion_rate >= 100.0:
        return "A"
    elif adhesion_rate >= 90.0:
        return "B"
    elif adhesion_rate >= 80.0:
        return "C"
    elif adhesion_rate >= 70.0:
        return "D"
    else:
        return "E"

# Compute the asphalt adhesion statistics
def compute_statistics(assessments: List[float], to_per_cents: bool = True) -> Dict[str, Union[float, str]]:
    average = np.mean(assessments)
    worst = min(assessments)
    stddev = np.std(assessments) if len(assessments) > 1 else 0.0
    
    if to_per_cents:
        print("Converting to percents")
        print(average, worst, stddev)
        average *= 100.0
        worst *= 100.0
        stddev *= 100.0

    return {
        "average": average,
        "stddev": stddev,
        "worst": worst,
        "average_classification": get_CSN_73_6161_classification(average),
        "worst_classification": get_CSN_73_6161_classification(worst),
    }

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
    # Prepare PDF content
    # as_buffer = False # for testing purposes
    if as_buffer:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=25*mm, bottomMargin=25*mm)
    else:
        doc = SimpleDocTemplate(f"test_report.pdf", pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=25*mm, bottomMargin=25*mm)
    pdf = []
    # Title
    pdf.append(PageBreak())
    pdf.append(Paragraph(_("Bitumen Adhesion Test Protocol"), styles["Title"]))

    n_samples = len(experiment_ids)
    text = _("""
    This report provides a comprehensive overview of the bitumen adhesion test protocol,
    with all relevant information according to the CSN 73 6161 standard.
    The adhesion test was performed on """) + f"{n_samples}" + _(""" samples of asphalt mixtures. The detailes about each specimen included below, the overview is at the end of the document.""")
    pdf.append(Paragraph(text, style_justify))
    pdf.append(Spacer(1, 0.6 * cm))

    text = _("""
    Both the visual expert assesment and the AI-based quantitative analysis are included in this report.
    If this two contradict each other, the visual expert assesment is considered the final result, however,
    the AI-based visualization is included for reference. 
    """)
    pdf.append(Paragraph(text, style_justify))
    pdf.append(Spacer(1, 0.2 * cm))

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
    list_.append([dat1, dat2])
    pdf = two_col_text_layout(pdf, list_, doc=doc)


    # Insert experiment records
    assessments_expert_guess = []
    assessments_automatic = []
    concerns = {"similar_images": 0, "old_images": 0}
    for experiment_id in experiment_ids:
        experiment = db_api.get_experiment_by_id(experiment_id)
        experiment.update({"timestamp": db_api.get_experiment_timestamp_by_id(experiment_id)})

        similar_dict = get_similar_experiment(experiment)

        # Add experiment record to PDF
        # pdf.append(PageBreak())
        # draw a line
        pdf.append(Spacer(1, 0.4 * cm))
        line = Drawing(doc.width ,1 * mm)
        line.add(Rect(0, 0, doc.width, 1 * mm, fillColor=colors.HexColor(REPORT_COLORS["topic_color"]), strokeWidth=0, strokeColor=colors.HexColor(REPORT_COLORS["topic_color"])))
        pdf.append(line)
        pdf.append(Spacer(1, 0.2 * cm))
        pdf = add_experiment_record(pdf, experiment, similar=similar_dict, doc=doc)
        
        original_image = memory_to_np_array(experiment.get("color"))
        if any(v is None for v in [experiment.get("mask_asphalt"), experiment.get("mask_aggregate")]):
            available_models = models.discover_models()
            if experiment.get("inference_model") in available_models:
                asphalt_mask, aggregate_mask, bg = models.inference_on_numpy(
                    np_image=original_image,
                    model_name=experiment.get("inference_model"),
                    session_id=user_id
                )
            else:
                model = experiment.get("inference_model", 'unknown')
                abort(500, description=_("Inference model") + model + _(' not available for experiment ID') + {id} + '.')    
                return None
        else:
            asphalt_mask = memory_to_np_array(experiment.get("mask_asphalt"))
            aggregate_mask = memory_to_np_array(experiment.get("mask_aggregate"))

        processed_image = process_image(
            original_image,
            asphalt_mask,
            aggregate_mask
        )
        pdf = add_images(
            pdf, 
            img_original=memory_to_np_array(experiment.get("color")), 
            img_processed=processed_image,
            similar_image=similar_dict if similar_dict else {},
            max_image_size_cm=[doc.width/2, doc.width/2],
            doc=doc
        )

        # Collect assessments
        assessments_expert_guess.append(float(experiment.get("expert_guess", None)))
        assessments_automatic.append(float(experiment.get("asphalt_ratio", None)))

        # Count suspicious cases
        if similar_dict:
            concerns["similar_images"] += 1

        experiment_date_str = str(experiment.get("timestamp", ''))
        experiment_date = pdl.parse(experiment_date_str) 
        print(experiment_date)
        print(report_date)
        if (report_date - experiment_date).days > 180:
            concerns["old_images"] += 1



    # Compute statistics
    stats_expert = compute_statistics(assessments_expert_guess)
    stats_automatic = compute_statistics(assessments_automatic)


    # PRINT FINAL SUMMARY
    # Final - table
    pdf.append(PageBreak())
    pdf.append(Paragraph(_("Tabular overview"), styles["Heading2"]))
    table_data = [[_("Specimen ID"), _("Visual Expert Assessment [%]"), _("AI-based Assesment  [%]")]]
    table_data.extend(
        [ items for items in zip(
            experiment_ids, 
            [f"{100*db_api.get_experiment_by_id(eid).get('expert_guess', 0):.2f}" for eid in experiment_ids],
            [f"{100*db_api.get_experiment_by_id(eid).get('asphalt_ratio', 0):.2f}" for eid in experiment_ids],
        )]
    )
    pdf = add_table(pdf, table_data, colWidths=[doc.width/3]*3)
    pdf.append(Spacer(1, 1.0 * cm))

    # Final summary + issues
    pdf.append(Paragraph(_("Report Conclusion"), styles["Heading2"]))
    pdf.append(Paragraph(_("Summary"), styles["Heading3"]))
    items = [
        Paragraph(_("The average adhesion rate across all samples is") + f" {stats_expert['average']:.2f} ± {stats_expert['stddev']:.2f} % " + _("according to expert visual assesment, which correspondes to calss") + f" {stats_expert['average_classification']} , ", style_justify),
        Paragraph(_("The average adhesion rate across all samples is") + f" {stats_automatic['average']:.2f} ± {stats_automatic['stddev']:.2f} % " + _("according to AI-based analysis, which correspondes to calss") + f" {stats_automatic['average_classification']} , ", style_justify),
        Paragraph(_("The worst adhesion rate (") +f"{stats_expert['worst']:.2f}" + _(" %) observed is class ") + f"{stats_expert['worst_classification']} " + _("according to expert visual assesment."), style_justify),
        Paragraph(_("The worst adhesion rate (") +f"{stats_automatic['worst']:.2f}" + _(" %) observed is class ") + f"{stats_automatic['worst_classification']} " + _("according to AI-based analysis."), style_justify),
    ]
    pdf = add_itemized_list(pdf, items)
    pdf.append(Paragraph(_("The final considered class is ") + f"{stats_expert['worst_classification']}", styles["Heading4"]))
    
    issues = []
    if concerns["similar_images"] > 0:
        issues.append(f"{concerns['similar_images']}/{len(experiment_ids)}" + _(" images seem to highly similar with others and might not be unique specimens."))
    if concerns["old_images"] > 0:
        issues.append(f"{concerns['old_images']}/{len(experiment_ids)}" + _(" have been uploaded more than 6 months ago."))
    if len(experiment_ids) < 2:
        issues.append(_("The report contains less than 2 samples, which is insufficient for CSN 73 6161 standard compliance."))
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
            print(_("Controlling employee:"), controlling_employee)
        except Exception:
            controlling_employee = user_info
    
    left_column = [
        Paragraph(_("The proceeding employee"), styles["Heading2"]),
        Paragraph(_("Name:") + f" {user_info.get('first_name', '-')} {user_info.get('last_name', '-')}", style_justify),
        Paragraph(_("Contact:") + f" {user_info.get('e_mail', '-')}", style_justify),
        Spacer(1, 1.2 * cm),
        Paragraph(_("Signature: ..................................................."), style_justify),
        Spacer(1, 0.4 * cm),
    ]

    right_column = [
        Paragraph(_("The controlling employee"), styles["Heading2"]),
        Paragraph(_("Name:") + f" {controlling_employee.get('first_name', '-')} {controlling_employee.get('last_name', '-')}", style_justify),
        Paragraph(_("Contact:") + f" {controlling_employee.get('e_mail', '-')}", style_justify),
        Spacer(1, 1.2 * cm),
        Paragraph(_("Signature: ..................................................."), style_justify),
        Spacer(1, 0.4 * cm),
    ]

    table_data = ["", ""]
    table_data.append([left_column, right_column])
    pdf = two_col_text_layout(pdf, table_data, doc=doc)

    pdf.append(Spacer(1, 1.0 * cm))
    pdf.append(Paragraph(_("This report was generated using AIBAL on ") + f"{report_date.to_datetime_string()}.", style_justify_right))

    doc.build(pdf,
        onFirstPage=lambda canvas, doc: first_page(canvas, doc, report_id=report_id),
        onLaterPages=lambda canvas, doc: styled_header_footer(canvas, doc, report_id=report_id)
    )
    
    if as_buffer:
        return buffer.getvalue()
    else:
        return None


def get_similar_experiment(experiment: Dict[str, Any]) -> Dict[str, Any]:  
    similar_ssim_id = experiment.get("similar_ssim_id", None)
    similar_ssim_value = experiment.get("similar_ssim_value", 0.0)
    similar_hist_id = experiment.get("similar_hist_id", None)
    similar_hist_value = experiment.get("similar_hist_value", 0.0)
    
    similar_hist_value = 0.0 if similar_hist_value is None else similar_hist_value
    similar_ssim_value = 0.0 if similar_ssim_value is None else similar_ssim_value

    similar_dict = {}
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
        f"{similar_experiment_id}" + _(" , uploaded by ") + f"{similar_user_e_mail}" + _(" on ") + f"{similar_date}" + \
        _(") with") + f" {100*similarity_score:.2f}% " + _("confidence ") + \
        _("using") + f" {similarity_method}. " + \
        _("""Please review the samples for potential duplication. In case the specimens clearly aren't duplicates, you can ignore this message.""")
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
    print("img 1 prossessed")
    img2 = get_printable_image(img_processed, max_image_size_cm)
    print("img 2 prossessed")
    table_data.append([_("Original Image"), _("Processed Image")])
    table_data.append([img1, img2])
    table_data.append(["", _("(Asphalt - RED, Aggregate - BLUE)")])
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
    img.save(buf, format="PNG")
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

    for key, value in experiment.items():
        if value is None or value == 'None':
            experiment[key] = '-'

    left_column = [
        Paragraph(_("Sample ID:") + f" {experiment.get('experiment_id', '-')}", styles["Heading3"]),
        Paragraph(_("Date:") + f" {experiment.get('info_datetime', '-')}", style_justify),
        Paragraph(_("Place of Experiment:") + f" {experiment.get('info_place_of_experiment', '-')}", style_justify),
        Paragraph(_("Sample Collection Data:") + f" {experiment.get('info_sample_collection_data', '-')}", style_justify),
        Paragraph(_("Wrapping temperature [°C]:") + f" {experiment.get('info_wrapping_temperature', '-')}", style_justify),
        Paragraph(_("Exposing water temperature [°C]:") + f" {experiment.get('info_exposing_water_temperature', '-')}", style_justify),
        Paragraph(_("Test procedure:") + f" {experiment.get('info_test_procedure', '-')}", style_justify),
    ]
    right_column = [
        Paragraph(_("Assessment - Adhesion Rate:"), styles["Heading4"]),
        Paragraph(_("Inference Model:") + f" {experiment.get('inference_model', '-')}", style_justify),
        Paragraph(_("Automatic Assessment [%]:") + f" {100*experiment.get('asphalt_ratio', '-'):.2f}", style_justify),
        Paragraph(_("Visual based Expert Guess [%]:") + f" {100*experiment.get('expert_guess', '-'):.2f}", style_justify),
        Paragraph(_("Comment:") + f" {experiment.get('comment', '-')}", style_justify),
    ]    
    table_data = [["", ""]]
    table_data.append([left_column, right_column])
    pdf = two_col_text_layout(pdf, table_data, doc=doc)
    pdf.append(Spacer(1, 0.2 * cm))
    return pdf    

def first_page(canvas, doc, report_id: str):
    canvas.saveState()

    width, height = doc.pagesize

    # Draw company logo (top-left)
    logo = PIL.Image.open("static/logo-text.png")
    logow, logoh = logo.size
    logo_scale = 120 * mm / logow

    # x position to center the image
    x = (width - logo_scale * logow) / 2

    # y position (from bottom) — here we keep your previous top margin calculation
    y = height - 110 * mm  # adjust as needed


    canvas.drawImage(
        "static/logo-text.png",
        x,
        y,
        width=logo_scale * logow,
        height=logo_scale * logoh,
        mask="auto"
    )
    

    canvas.setFillColor(colors.HexColor(REPORT_COLORS["topic_color"]))
    rect_width = 210 * mm
    rect_height = 120 * mm
    rect_x = (width - rect_width) / 2 
    rect_y = height - 200 * mm - rect_height / 2
    canvas.setStrokeColor(colors.black)
    canvas.setStrokeAlpha(0)
    canvas.rect(rect_x, rect_y, rect_width, rect_height, fill=1)


    # -------------------
    # Draw a line
    # -------------------
    # canvas.setStrokeColor(colors.green)
    # canvas.setLineWidth(1.5)
    # canvas.line(10*mm, 10*mm, width - 10*mm, 50*mm)

    # -------------------
    # Draw some text
    # -------------------
    canvas.setFont("DejaVu-Bold", 14)
    # canvas.setFont("DejaVu-Bold", 14)
    canvas.setFillColor(colors.black)
    # canvas.drawString(50*mm, height - 70*mm, "Hello, ReportLab Drawing!")


    # Draw report title (centered)
    canvas.restoreState()
    canvas.setFillColor(colors.white)
    canvas.setFont("DejaVu-Bold", 36)
    canvas.drawCentredString(
        width / 2,
        height - 200 * mm,
        "AIBAL Report",    )
    canvas.saveState()
    PageBreak()

def styled_header_footer(canvas, doc, report_id: str):
    canvas.saveState()

    width, height = doc.pagesize

    header_height = 18 * mm
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

    # Header bottom line
    canvas.setStrokeColor(colors.white)
    canvas.setLineWidth(0.0)
    canvas.line(
        doc.leftMargin,
        height - header_height,
        width - doc.rightMargin,
        height - header_height
    )

    # Header text
    canvas.setFillColor(colors.white)
    canvas.setFont("DejaVu-Bold", 11)
    canvas.drawString(
        doc.leftMargin,
        height - header_height + 6 * mm,
        "AIBAL Report"
    )

    # ======================
    # Footer separator line
    # ======================
    canvas.setStrokeColor(colors.grey)
    canvas.setLineWidth(0.5)
    canvas.line(
        doc.leftMargin,
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
        f"Page {doc.page}"  # Assuming doc.pageCount is defined elsewhere
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
    ]))

    table._argH[0] = 0 # first row height to 0
    pdf.append(table)
    
    return pdf

def party_details_data(pdf: list, party_info: Dict[str, Any]) -> list:
    data = [
        Paragraph(f"{party_info.get('Caption', 'Party Details')}", styles["Heading2"]),
        Paragraph(_("Name:") + f" {party_info.get('name', '-')}", style_justify),
        Paragraph(_("Address:") + f" {party_info.get('address', '-')}", style_justify),
        Paragraph(_("Contact:") + f" {party_info.get('contact', '-')}", style_justify),
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