"""
Pure-Python PowerPoint (.pptx) Generator for VideoLearn AI.
Generates genuine Microsoft Office OpenXML (.pptx) presentations without external dependencies.
Fully compatible with Microsoft PowerPoint, Google Slides, Apple Keynote, and LibreOffice.
"""

import io
import zipfile
import xml.sax.saxutils as saxutils
from typing import List, Dict, Any


def escape_xml(text: str) -> str:
    """Safely escape text for XML inclusion."""
    if not text:
        return ""
    return saxutils.escape(str(text))


class PurePPTXBuilder:
    """
    Builds standard ECMA-376 PresentationML (.pptx) files using Python's built-in zipfile and XML.
    """

    def __init__(self, title: str = "影片教材簡報", subtitle: str = "VideoLearn AI 學術研討教材"):
        self.title = title
        self.subtitle = subtitle
        self.slides: List[Dict[str, Any]] = []

    def add_slide(self, title: str, bullets: List[str], notes: str = "", category: str = "重點教學"):
        """Add a content slide with title, bullet points, and speaker notes."""
        self.slides.append({
            "title": title,
            "bullets": bullets,
            "notes": notes,
            "category": category
        })

    def build_bytes(self) -> bytes:
        """Construct the .pptx zip archive in memory and return bytes."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. [Content_Types].xml
            zf.writestr("[Content_Types].xml", self._get_content_types_xml())

            # 2. _rels/.rels
            zf.writestr("_rels/.rels", self._get_root_rels_xml())

            # 3. docProps
            zf.writestr("docProps/app.xml", self._get_app_props_xml())
            zf.writestr("docProps/core.xml", self._get_core_props_xml())

            # 4. ppt/_rels/presentation.xml.rels
            zf.writestr("ppt/_rels/presentation.xml.rels", self._get_pres_rels_xml())

            # 5. ppt/presentation.xml
            zf.writestr("ppt/presentation.xml", self._get_presentation_xml())

            # 6. ppt/slideLayouts and slideMasters
            zf.writestr("ppt/slideLayouts/slideLayout1.xml", self._get_slide_layout_xml())
            zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", self._get_slide_layout_rels_xml())
            zf.writestr("ppt/slideMasters/slideMaster1.xml", self._get_slide_master_xml())
            zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", self._get_slide_master_rels_xml())

            # 7. ppt/theme/theme1.xml
            zf.writestr("ppt/theme/theme1.xml", self._get_theme_xml())

            # 8. Individual slides
            # Slide 1 is Title Slide
            zf.writestr("ppt/slides/slide1.xml", self._get_title_slide_xml())
            zf.writestr("ppt/slides/_rels/slide1.xml.rels", self._get_slide_rels_xml())

            # Slide 2..N are content slides
            for idx, slide_data in enumerate(self.slides, start=2):
                zf.writestr(f"ppt/slides/slide{idx}.xml", self._get_content_slide_xml(slide_data, idx))
                zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", self._get_slide_rels_xml())

        buffer.seek(0)
        return buffer.getvalue()

    def save_to_file(self, filepath: str):
        """Save the generated .pptx to a file path."""
        content = self.build_bytes()
        with open(filepath, 'wb') as f:
            f.write(content)

    # ------------------ XML Templates ------------------

    def _get_content_types_xml(self) -> str:
        slide_parts = "".join(
            f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
            for i in range(1, len(self.slides) + 2)
        )
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  {slide_parts}
</Types>"""

    def _get_root_rels_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

    def _get_app_props_xml(self) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>VideoLearn AI Generator</Application>
  <Slides>{len(self.slides) + 1}</Slides>
</Properties>"""

    def _get_core_props_xml(self) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape_xml(self.title)}</dc:title>
  <dc:creator>VideoLearn AI Educational Agent</dc:creator>
  <cp:lastModifiedBy>VideoLearn AI</cp:lastModifiedBy>
  <dc:description>一切資源作學術研討幫助學習者學習，不提供商業用、或搬運影片用</dc:description>
</cp:coreProperties>"""

    def _get_pres_rels_xml(self) -> str:
        slide_rels = "".join(
            f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
            for i in range(1, len(self.slides) + 2)
        )
        theme_rel_id = f"rId{len(self.slides) + 2}"
        master_rel_id = f"rId{len(self.slides) + 3}"
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
  {slide_rels}
  <Relationship Id="{theme_rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>"""

    def _get_presentation_xml(self) -> str:
        slide_ids = "".join(
            f'<p:sldId id="{255 + i}" r:id="rId{i+1}"/>'
            for i in range(1, len(self.slides) + 2)
        )
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:sldMasterIdLst>
    <p:sldMasterId id="2147483648" r:id="rId1"/>
  </p:sldMasterIdLst>
  <p:sldIdLst>
    {slide_ids}
  </p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""

    def _get_slide_rels_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>"""

    def _get_slide_layout_rels_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""

    def _get_slide_master_rels_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""

    def _get_slide_layout_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" type="titleAndContent">
  <p:cSld name="Title and Content">
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr/>
    </p:spTree>
  </p:cSld>
</p:sldLayout>"""

    def _get_slide_master_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr/>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst>
    <p:sldLayoutId id="2147483649" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>
  </p:sldLayoutIdLst>
</p:sldMaster>"""

    def _get_theme_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="VideoLearn Modern Education">
  <a:themeElements>
    <a:clrScheme name="Ocean Indigo">
      <a:dk1><a:srgbClr val="0F172A"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1E293B"/></a:dk2>
      <a:lt2><a:srgbClr val="F8FAFC"/></a:lt2>
      <a:accent1><a:srgbClr val="2563EB"/></a:accent1>
      <a:accent2><a:srgbClr val="0D9488"/></a:accent2>
      <a:accent3><a:srgbClr val="F59E0B"/></a:accent3>
      <a:accent4><a:srgbClr val="6366F1"/></a:accent4>
      <a:accent5><a:srgbClr val="10B981"/></a:accent5>
      <a:accent6><a:srgbClr val="EC4899"/></a:accent6>
      <a:hlink><a:srgbClr val="1D4ED8"/></a:hlink>
      <a:folHlink><a:srgbClr val="6D28D9"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Modern Sans">
      <a:majorFont><a:latin typeface="Noto Sans TC"/><a:ea typeface="Noto Sans TC"/></a:majorFont>
      <a:minorFont><a:latin typeface="Noto Sans TC"/><a:ea typeface="Noto Sans TC"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
  </a:themeElements>
</a:theme>"""

    def _get_title_slide_xml(self) -> str:
        """First slide: Elegant Dark Blue title slide with Academic Fair Use notice."""
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <!-- Background Header Banner -->
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="HeaderBanner"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="0" y="0"/><a:ext cx="12192000" cy="6858000"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:solidFill><a:srgbClr val="0F172A"/></a:solidFill>
        </p:spPr>
      </p:sp>
      <!-- Title text box -->
      <p:sp>
        <p:nvSpPr><p:cNvPr id="3" name="TitleBox"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="1000000" y="1600000"/><a:ext cx="10192000" cy="2200000"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:noFill/>
        </p:spPr>
        <p:txBody>
          <a:bodyPr anchor="ctr" wrap="square"/>
          <a:lstStyle/>
          <a:p>
            <a:pPr algn="ctr"/>
            <a:r>
              <a:rPr lang="zh-TW" sz="4400" b="1">
                <a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>
              </a:rPr>
              <a:t>{escape_xml(self.title)}</a:t>
            </a:r>
          </a:p>
          <a:p>
            <a:pPr algn="ctr"/>
            <a:r>
              <a:rPr lang="zh-TW" sz="2400">
                <a:solidFill><a:srgbClr val="60A5FA"/></a:solidFill>
              </a:rPr>
              <a:t>{escape_xml(self.subtitle)}</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
      <!-- Fair Use Badge Banner -->
      <p:sp>
        <p:nvSpPr><p:cNvPr id="4" name="FairUseNotice"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="1500000" y="4800000"/><a:ext cx="9192000" cy="1100000"/></a:xfrm>
          <a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>
          <a:solidFill><a:srgbClr val="1E293B"/></a:solidFill>
          <a:ln w="25400"><a:solidFill><a:srgbClr val="3B82F6"/></a:solidFill></a:ln>
        </p:spPr>
        <p:txBody>
          <a:bodyPr anchor="ctr" wrap="square"/>
          <a:lstStyle/>
          <a:p>
            <a:pPr algn="ctr"/>
            <a:r>
              <a:rPr lang="zh-TW" sz="1600" b="1">
                <a:solidFill><a:srgbClr val="FDE047"/></a:solidFill>
              </a:rPr>
              <a:t>⚖️ 學術研討與教育合理使用聲明</a:t>
            </a:r>
          </a:p>
          <a:p>
            <a:pPr algn="ctr"/>
            <a:r>
              <a:rPr lang="zh-TW" sz="1300">
                <a:solidFill><a:srgbClr val="94A3B8"/></a:solidFill>
              </a:rPr>
              <a:t>一切資源作學術研討幫助學習者學習，不提供商業用、或搬運影片用</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""

    def _get_content_slide_xml(self, slide: Dict[str, Any], slide_num: int) -> str:
        """Content slide: clean modern layout with colored category header, title, and bullet cards."""
        bullets_xml = []
        start_y = 1900000
        step_y = 900000

        for i, bullet in enumerate(slide["bullets"][:5]):
            cur_y = start_y + (i * step_y)
            bullet_clean = escape_xml(bullet)
            bullets_xml.append(f"""
      <p:sp>
        <p:nvSpPr><p:cNvPr id="{10 + i}" name="Bullet_{i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="1000000" y="{cur_y}"/><a:ext cx="10192000" cy="750000"/></a:xfrm>
          <a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>
          <a:solidFill><a:srgbClr val="F8FAFC"/></a:solidFill>
          <a:ln w="12700"><a:solidFill><a:srgbClr val="E2E8F0"/></a:solidFill></a:ln>
        </p:spPr>
        <p:txBody>
          <a:bodyPr anchor="ctr" lIns="200000" wrap="square"/>
          <a:lstStyle/>
          <a:p>
            <a:r>
              <a:rPr lang="zh-TW" sz="1800">
                <a:solidFill><a:srgbClr val="1E293B"/></a:solidFill>
              </a:rPr>
              <a:t>• {bullet_clean}</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>""")

        bullets_combined = "\n".join(bullets_xml)

        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvSpPr>
      <p:grpSpPr/>
      <!-- Top Accent Bar -->
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="AccentBar"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="0" y="0"/><a:ext cx="12192000" cy="140000"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:solidFill><a:srgbClr val="2563EB"/></a:solidFill>
        </p:spPr>
      </p:sp>
      <!-- Category Tag & Slide Title -->
      <p:sp>
        <p:nvSpPr><p:cNvPr id="3" name="TitleArea"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="1000000" y="450000"/><a:ext cx="10192000" cy="1200000"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:noFill/>
        </p:spPr>
        <p:txBody>
          <a:bodyPr anchor="t" wrap="square"/>
          <a:lstStyle/>
          <a:p>
            <a:r>
              <a:rPr lang="zh-TW" sz="1300" b="1">
                <a:solidFill><a:srgbClr val="2563EB"/></a:solidFill>
              </a:rPr>
              <a:t>[{escape_xml(slide.get('category', '重點章節'))}]</a:t>
            </a:r>
          </a:p>
          <a:p>
            <a:r>
              <a:rPr lang="zh-TW" sz="3000" b="1">
                <a:solidFill><a:srgbClr val="0F172A"/></a:solidFill>
              </a:rPr>
              <a:t>{escape_xml(slide['title'])}</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
      <!-- Content Items -->
      {bullets_combined}
      <!-- Footer Note -->
      <p:sp>
        <p:nvSpPr><p:cNvPr id="30" name="Footer"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="1000000" y="6400000"/><a:ext cx="10192000" cy="350000"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:noFill/>
        </p:spPr>
        <p:txBody>
          <a:bodyPr anchor="b" wrap="square"/>
          <a:lstStyle/>
          <a:p>
            <a:r>
              <a:rPr lang="zh-TW" sz="1000">
                <a:solidFill><a:srgbClr val="94A3B8"/></a:solidFill>
              </a:rPr>
              <a:t>VideoLearn AI • 學術研討教育教材 (第 {slide_num} 頁) • 非商業用途</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""
