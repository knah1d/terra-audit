local page_break = pandoc.RawBlock("openxml", '<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
function Header(header)
  if FORMAT:match("docx") and header.level == 1 then return { page_break, header } end
end
