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
def process(name):
    src=Path(name)
    with tempfile.TemporaryDirectory(prefix="terra-srs-docx-") as td:
        tmp=Path(td)
        with zipfile.ZipFile(src) as z: z.extractall(tmp)
        xml=tmp/"word/document.xml"; tree=ET.parse(xml); root=tree.getroot(); body=root.find("w:body",NS)
        sect=body.find("w:sectPr",NS); size=ensure(sect,"w:pgSz"); size.set(qn("w:w"),"11906"); size.set(qn("w:h"),"16838")
        margins=ensure(sect,"w:pgMar")
        for side in ("top","right","bottom","left"): margins.set(qn("w:"+side),"1440")
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
