-- One public entry point for inline and modal views; Quarto owns image resources.
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
    local mode = value(rawget(kwargs, 'mode')) or 'button'
    if mode ~= 'button' and mode ~= 'inline' then return invalid('mode must be button or inline.') end
    if #args > 0 or (target == nil) == (src == nil) then
      return invalid('specify exactly one of target or src (named arguments).')
    end
    for key, _ in pairs(kwargs) do
      if key ~= 'target' and key ~= 'src' and key ~= 'label' and key ~= 'mode' then
        return invalid('unknown argument ' .. key)
      end
    end
    local label = value(rawget(kwargs, 'label')) or 'View image'
    if label == '' or target == '' or src == '' then
      return invalid('target, src, and label must not be empty.')
    end
    if not quarto.doc.is_format('html:js') then
      if mode == 'inline' then
        if target then return pandoc.Inlines({}) end
        return pandoc.Image({pandoc.Str(label)}, src)
      end
      return pandoc.Link({pandoc.Str(label)}, target and ('#' .. target) or src)
    end
    if meta['askr-viewer-disabled'] == true or (meta.lightbox == false and meta['askr-viewer-disabled'] == nil) then
      return invalid('lightbox: false conflicts with an image-view button. Remove the button or enable Lightbox.')
    end
    serial = serial + 1
    local id = 'askr-image-entry-' .. serial
    if mode == 'inline' and context == 'inline' then return invalid('inline mode requires a standalone shortcode block.') end
    local button_attr = pandoc.Attr('', {'askr-image-button-entry'}, {['data-askr-image-target']=target or id, ['data-askr-image-mode']=mode})
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
      -- A real Pandoc image lets Quarto own resource copying; this entry is explicit.
      blocks[#blocks + 1] = pandoc.Div({pandoc.Para({
        pandoc.Image({}, src, '', pandoc.Attr(id, {'lightbox'}))
      })}, pandoc.Attr('', {'askr-image-source'}, {['aria-hidden']='true'}))
    end
    blocks[#blocks + 1] = pandoc.Div({pandoc.Para({pandoc.Str(label)})}, button_attr)
    return pandoc.Blocks(blocks)
  end
}
