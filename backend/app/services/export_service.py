import io
from typing import Dict, Any
from datetime import datetime

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import markdown as md


class ExportService:
    """成果导出服务

    支持将访谈成果导出为多种格式：Markdown、Word(docx)、PDF。
    """

    @classmethod
    def export_markdown(cls, content: str, filename_base: str) -> tuple:
        """导出为Markdown格式
        
        Returns: (bytes, filename)
        """
        data = content.encode("utf-8")
        filename = f"{filename_base}.md"
        return data, filename

    @classmethod
    def export_docx(cls, content: str, title: str, filename_base: str) -> tuple:
        """导出为Word文档格式
        
        将Markdown内容解析并转换为格式化的Word文档。
        Returns: (bytes, filename)
        """
        doc = Document()
        
        # 设置默认字体
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Microsoft YaHei'
        font.size = Pt(11)
        
        # 添加标题
        heading = doc.add_heading(title, level=0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 添加生成时间
        time_para = doc.add_paragraph()
        time_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = time_para.add_run(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(128, 128, 128)
        
        doc.add_paragraph()  # 空行
        
        # 简单解析Markdown并转换为Word段落
        # 这里做一个简化的逐行解析
        lines = content.split('\n')
        i = 0
        in_code_block = False
        code_lines = []
        
        while i < len(lines):
            line = lines[i]
            
            # 代码块处理
            if line.strip().startswith('```'):
                if in_code_block:
                    # 结束代码块
                    if code_lines:
                        p = doc.add_paragraph()
                        p.style = 'Intense Quote'
                        p.add_run('\n'.join(code_lines))
                    code_lines = []
                    in_code_block = False
                else:
                    in_code_block = True
                i += 1
                continue
            
            if in_code_block:
                code_lines.append(line)
                i += 1
                continue
            
            stripped = line.strip()
            if not stripped:
                i += 1
                continue
            
            # 标题
            if stripped.startswith('# '):
                doc.add_heading(stripped[2:], level=1)
            elif stripped.startswith('## '):
                doc.add_heading(stripped[3:], level=2)
            elif stripped.startswith('### '):
                doc.add_heading(stripped[4:], level=3)
            elif stripped.startswith('#### '):
                doc.add_heading(stripped[5:], level=4)
            # 引用
            elif stripped.startswith('>'):
                p = doc.add_paragraph()
                p.style = 'Quote'
                p.add_run(stripped[1:].strip())
            # 列表项
            elif stripped.startswith('- ') or stripped.startswith('* '):
                text = stripped[2:]
                # 处理粗体
                p = doc.add_paragraph(text, style='List Bullet')
            elif stripped.startswith('  - '):
                text = stripped[4:]
                p = doc.add_paragraph(text, style='List Bullet 2')
            elif stripped.startswith('    - '):
                text = stripped[6:]
                p = doc.add_paragraph(text, style='List Bullet 3')
            # 数字列表
            elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1] == '.':
                text = stripped[stripped.find(' ') + 1:]
                p = doc.add_paragraph(text, style='List Number')
            # 普通段落
            else:
                p = doc.add_paragraph(stripped)
            
            i += 1
        
        # 保存到内存
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        filename = f"{filename_base}.docx"
        return buffer.getvalue(), filename

    @classmethod
    def export_pdf(cls, content: str, title: str, filename_base: str) -> tuple:
        """导出为PDF格式

        由于完整的PDF生成需要较重的依赖（如weasyprint/reportlab），
        当前实现将Markdown转为HTML后返回，由前端或浏览器进行打印/PDF转换。
        
        Returns: (bytes, filename)
        """
        html_content = md.markdown(
            content,
            extensions=['tables', 'fenced_code', 'toc'],
        )
        
        full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.8; color: #333; }}
h1 {{ color: #1a1a1a; border-bottom: 2px solid #4f46e5; padding-bottom: 10px; }}
h2 {{ color: #333; margin-top: 30px; border-left: 4px solid #4f46e5; padding-left: 12px; }}
h3 {{ color: #444; margin-top: 20px; }}
blockquote {{ border-left: 4px solid #ddd; padding-left: 16px; color: #666; margin: 0; }}
code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
pre {{ background: #f4f4f4; padding: 16px; border-radius: 6px; overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
th {{ background: #f8f8f8; }}
ul, ol {{ padding-left: 20px; }}
</style>
</head>
<body>
{html_content}
</body>
</html>"""
        
        data = full_html.encode("utf-8")
        filename = f"{filename_base}.html"
        return data, filename

    @classmethod
    def export_json(cls, data: Dict[str, Any], filename_base: str) -> tuple:
        """导出为JSON格式
        
        Returns: (bytes, filename)
        """
        import json
        content = json.dumps(data, ensure_ascii=False, indent=2)
        data_bytes = content.encode("utf-8")
        filename = f"{filename_base}.json"
        return data_bytes, filename
