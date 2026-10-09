-- Askr button entries reuse Quarto's native Lightbox; no independent image runtime.
local serial = 0
local function value(v)
  return v and pandoc.utils.stringify(v) or nil
end
local function invalid(message)
  -- Quarto replaces Lua error() with a logger; assert raises in every output format.
  assert(false, 'askr-image-view: ' .. message)
end

return {
  ['askr-image-view'] = function(args, kwargs, meta, raw_args, context)
    local target, src = value(rawget(kwargs, 'target')), value(rawget(kwargs, 'src'))
    if #args > 0 or (target == nil) == (src == nil) then
      return invalid('specify exactly one of target or src (named arguments).')
    end
    for key, _ in pairs(kwargs) do
      if key ~= 'target' and key ~= 'src' and key ~= 'label' then
        return invalid('unknown argument ' .. key)
      end
    end
    local label = value(rawget(kwargs, 'label')) or 'View image'
    if label == '' or target == '' or src == '' then
      return invalid('target, src, and label must not be empty.')
    end
    if not quarto.doc.is_format('html:js') then
      return pandoc.Link({pandoc.Str(label)}, target and ('#' .. target) or src)
    end
    if meta.lightbox == false then
      return invalid('lightbox: false conflicts with an image-view button. Remove the button or enable Lightbox.')
    end
    serial = serial + 1
    local id = 'askr-image-entry-' .. serial
    local button_attr = pandoc.Attr('', {'askr-image-button-entry'}, {['data-askr-image-target']=target or id})
    if context == 'inline' then
      local inlines = {}
      if src then
        inlines[#inlines + 1] = pandoc.Span({pandoc.Image({}, src, '', pandoc.Attr(id, {'lightbox'}))},
          pandoc.Attr('', {'askr-image-source'}, {['aria-hidden']='true'}))
      end
      inlines[#inlines + 1] = pandoc.Span({pandoc.Str(label)}, button_attr)
      return pandoc.Inlines(inlines)
    end
    local blocks = {}
    if src then
      -- A real Pandoc image lets Quarto own resource copying and Lightbox registration.
      blocks[#blocks + 1] = pandoc.Div({pandoc.Para({
        pandoc.Image({}, src, '', pandoc.Attr(id))
      })}, pandoc.Attr('', {'askr-image-source'}, {['aria-hidden']='true'}))
    end
    blocks[#blocks + 1] = pandoc.Div({pandoc.Para({pandoc.Str(label)})}, button_attr)
    return pandoc.Blocks(blocks)
  end
}
