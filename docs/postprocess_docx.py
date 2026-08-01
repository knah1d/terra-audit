#!/usr/bin/env python3
from pathlib import Path
import shutil, sys, tempfile, xml.etree.ElementTree as ET, zipfile
W="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A="http://schemas.openxmlformats.org/drawingml/2006/main"
NS={"w":W,"wp":WP,"a":A}
ET.register_namespace("w",W); ET.register_namespace("wp",WP); ET.register_namespace("a",A)
def qn(n): return f"{{{W}}}{n.split(':')[1]}"
def ensure(p,n):
    c=p.find(n,NS)
    return c if c is not None else ET.SubElement(p,qn(n))
def text(p): return "".join(n.text or "" for n in p.findall(".//w:t",NS))
TABLE_BORDER_COLOR="4F81BD"
COVER_TITLE_COLOR="1155CC"
COVER_RED="C00000"
COVER_SUBTITLE_GRAY="333333"
def ensure_char_style(root,style_id,name,color,size,bold=True,italic=False):
    style=None
    for style in root.findall("w:style",NS):
        if style.get(qn("w:styleId"))==style_id:
            break
    else:
        style=ET.SubElement(root,qn("w:style"))
        style.set(qn("w:type"),"character"); style.set(qn("w:styleId"),style_id)
    style_name=ensure(style,"w:name"); style_name.set(qn("w:val"),name)
    based=ensure(style,"w:basedOn"); based.set(qn("w:val"),"DefaultParagraphFont")
    rpr=ensure(style,"w:rPr")
    for tag in ("w:b","w:i","w:color","w:sz","w:szCs"):
        old=rpr.find(tag,NS)
        if old is not None: rpr.remove(old)
    if bold:
        b=ET.SubElement(rpr,qn("w:b")); b.set(qn("w:val"),"1")
    if italic:
        i=ET.SubElement(rpr,qn("w:i")); i.set(qn("w:val"),"1")
    c=ET.SubElement(rpr,qn("w:color")); c.set(qn("w:val"),color)
    sz=ET.SubElement(rpr,qn("w:sz")); sz.set(qn("w:val"),str(size))
    szCs=ET.SubElement(rpr,qn("w:szCs")); szCs.set(qn("w:val"),str(size))
def ensure_para_style(root,style_id,name,jc=None,border=False):
    style=None
    for style in root.findall("w:style",NS):
        if style.get(qn("w:styleId"))==style_id:
            break
    else:
        style=ET.SubElement(root,qn("w:style"))
        style.set(qn("w:type"),"paragraph"); style.set(qn("w:styleId"),style_id)
    style_name=ensure(style,"w:name"); style_name.set(qn("w:val"),name)
    based=ensure(style,"w:basedOn"); based.set(qn("w:val"),"Normal")
    ppr=ensure(style,"w:pPr")
    if jc:
        j=ensure(ppr,"w:jc"); j.set(qn("w:val"),jc)
    if border:
        pbdr=ensure(ppr,"w:pBdr")
        bottom=ensure(pbdr,"w:bottom")
        bottom.set(qn("w:val"),"single"); bottom.set(qn("w:sz"),"6")
        bottom.set(qn("w:space"),"1"); bottom.set(qn("w:color"),"BFBFBF")
def set_cover_styles(styles_path):
    tree=ET.parse(styles_path); root=tree.getroot()
    ensure_char_style(root,"CoverTitleBlue","Cover Title Blue",COVER_TITLE_COLOR,44)
    ensure_char_style(root,"CoverSubtitleItalic","Cover Subtitle Italic",COVER_SUBTITLE_GRAY,22,bold=False,italic=True)
    ensure_char_style(root,"CoverRedHeader","Cover Red Header",COVER_RED,22)
    ensure_para_style(root,"CoverCenter","Cover Center",jc="center")
    ensure_para_style(root,"CoverRule","Cover Rule",jc="center",border=True)
    tree.write(styles_path,encoding="UTF-8",xml_declaration=True)
def strip_first_table_borders(document_xml_path):
    tree=ET.parse(document_xml_path); root=tree.getroot()
    table=root.find(".//w:tbl",NS)
    if table is None: return
    tbl_pr=ensure(table,"w:tblPr")
    borders=ET.Element(qn("w:tblBorders"))
    for edge in ("top","left","bottom","right","insideH","insideV"):
        el=ET.SubElement(borders,qn("w:"+edge)); el.set(qn("w:val"),"none")
    tbl_style=tbl_pr.find("w:tblStyle",NS)
    tbl_pr.insert(list(tbl_pr).index(tbl_style)+1 if tbl_style is not None else 0,borders)
    tree.write(document_xml_path,encoding="UTF-8",xml_declaration=True)
def center_first_table(document_xml_path):
    tree=ET.parse(document_xml_path); root=tree.getroot()
    table=root.find(".//w:tbl",NS)
    if table is None: return
    tbl_pr=ensure(table,"w:tblPr")
    jc=ensure(tbl_pr,"w:jc"); jc.set(qn("w:val"),"center")
    for paragraph in table.findall(".//w:p",NS):
        ppr=ensure(paragraph,"w:pPr")
        align=ensure(ppr,"w:jc"); align.set(qn("w:val"),"center")
    tree.write(document_xml_path,encoding="UTF-8",xml_declaration=True)
def make_cover_section(body, final_section):
    for paragraph in body.findall("w:p",NS):
        page_break=paragraph.find('.//w:br[@w:type="page"]',NS)
        if page_break is None: continue
        for run in paragraph.findall("w:r",NS):
            if run.find('w:br[@w:type="page"]',NS) is not None:
                paragraph.remove(run)
        ppr=ensure(paragraph,"w:pPr")
        section=ensure(ppr,"w:sectPr")
        section_type=ensure(section,"w:type")
        section_type.set(qn("w:val"),"nextPage")
        final_size=final_section.find("w:pgSz",NS)
        size=ensure(section,"w:pgSz")
        if final_size is not None:
            size.attrib.update(final_size.attrib)
        final_margins=final_section.find("w:pgMar",NS)
        margins=ensure(section,"w:pgMar")
        if final_margins is not None:
            margins.attrib.update(final_margins.attrib)
        borders=ensure(section,"w:pgBorders")
        borders.set(qn("w:offsetFrom"),"page")
        for edge in ("top","left","bottom","right"):
            border=ensure(borders,"w:"+edge)
            border.set(qn("w:val"),"single")
            border.set(qn("w:sz"),"6")
            border.set(qn("w:space"),"24")
            border.set(qn("w:color"),"B7B7B7")
        return
def set_table_borders(styles_path):
    tree=ET.parse(styles_path); root=tree.getroot()
    for style in root.findall("w:style",NS):
        if style.get(qn("w:styleId"))=="Table":
            tbl_pr=ensure(style,"w:tblPr")
            borders=ET.Element(qn("w:tblBorders"))
            for edge in ("top","left","bottom","right","insideH","insideV"):
                el=ET.SubElement(borders,qn("w:"+edge))
                el.set(qn("w:val"),"single"); el.set(qn("w:sz"),"4")
                el.set(qn("w:space"),"0"); el.set(qn("w:color"),TABLE_BORDER_COLOR)
            tbl_ind=tbl_pr.find("w:tblInd",NS)
            tbl_pr.insert(list(tbl_pr).index(tbl_ind)+1 if tbl_ind is not None else 0,borders)
            tree.write(styles_path,encoding="UTF-8",xml_declaration=True)
            return
def process(name):
    src=Path(name)
    with tempfile.TemporaryDirectory(prefix="terra-srs-docx-") as td:
        tmp=Path(td)
        with zipfile.ZipFile(src) as z: z.extractall(tmp)
        set_table_borders(tmp/"word/styles.xml")
        set_cover_styles(tmp/"word/styles.xml")
        xml=tmp/"word/document.xml"
        strip_first_table_borders(xml)
        center_first_table(xml)
        tree=ET.parse(xml); root=tree.getroot(); body=root.find("w:body",NS)
        sect=body.find("w:sectPr",NS); size=ensure(sect,"w:pgSz"); size.set(qn("w:w"),"11906"); size.set(qn("w:h"),"16838")
        margins=ensure(sect,"w:pgMar")
        for side in ("top","right","bottom","left"): margins.set(qn("w:"+side),"1440")
        make_cover_section(body,sect)
        for table in root.findall(".//w:tbl",NS):
            rows=table.findall("w:tr",NS)
            if rows: ensure(ensure(rows[0],"w:trPr"),"w:tblHeader")
            for row in rows: ensure(ensure(row,"w:trPr"),"w:cantSplit")
        children=list(body)
        for i,p in enumerate(children):
            if p.tag==qn("w:p") and p.find(".//w:drawing",NS) is not None:
                drawing=p.find(".//w:drawing",NS)
                extent=drawing.find(".//wp:extent",NS)
                if extent is not None:
                    width=int(extent.get("cx")); height=int(extent.get("cy"))
                    max_width=int(6.2*914400); max_height=int(8.5*914400)
                    scale=min(1.0,max_width/width,max_height/height)
                    if scale < 1.0:
                        width=round(width*scale); height=round(height*scale)
                        extent.set("cx",str(width)); extent.set("cy",str(height))
                        for transform_extent in drawing.findall(".//a:xfrm/a:ext",NS):
                            transform_extent.set("cx",str(width)); transform_extent.set("cy",str(height))
                ensure(ensure(p,"w:pPr"),"w:keepNext")
                if i+1<len(children) and children[i+1].tag==qn("w:p") and text(children[i+1]).strip().startswith("Fig "):
                    props=ensure(children[i+1],"w:pPr"); style=ensure(props,"w:pStyle"); style.set(qn("w:val"),"Caption"); ensure(props,"w:keepLines")
        tree.write(xml,encoding="UTF-8",xml_declaration=True)
        out=src.with_suffix(".postprocessed.docx")
        with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
            for p in tmp.rglob("*"):
                if p.is_file(): z.write(p,p.relative_to(tmp))
        shutil.move(out,src)
if __name__=="__main__": process(sys.argv[1])
