-- Capture the original Math source before rendering; never reconstruct TeX
-- from MathJax output or require authors to maintain a second formula.
local function escape_html(text)
  return text:gsub('&', '&amp;'):gsub('<', '&lt;'):gsub('>', '&gt;'):gsub('"', '&quot;'):gsub('\r', '&#13;')
end

function Para(block)
  if not quarto.doc.is_format('html') or #block.content ~= 1 then return nil end
  local math = block.content[1]
  if math.t ~= 'Math' or math.mathtype ~= 'DisplayMath' then return nil end
  local controls = pandoc.RawBlock('html',
    '<div class="askr-math-actions"><button type="button" class="askr-math-copy" aria-label="Copy LaTeX">Copy</button>' ..
    '<span class="askr-math-status" role="status" aria-live="polite"></span></div>')
  local source = pandoc.RawBlock('html',
    '<div class="askr-math-source" hidden><label>LaTeX source' ..
    -- HTML discards the first LF in a textarea; supply our own, not the source's.
    '<textarea readonly aria-label="LaTeX source" spellcheck="false">\n' ..
    escape_html(math.text) .. '</textarea></label></div>')
  return pandoc.Div({controls, block, source}, pandoc.Attr('', {'askr-copyable-math'}))
end
