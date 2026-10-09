-- Capture author settings before Quarto's Lightbox filter. Askr owns the only
-- viewer runtime; Quarto still owns figures, cross references and resource paths.
function Pandoc(doc)
  if not quarto.doc.is_format('html:js') then return doc end
  quarto.doc.add_html_dependency({name='askr-image-viewer', version='1', scripts={'image-viewer.js'}, stylesheets={'image-viewer.css'}})
  local settings = doc.meta.lightbox
  local disabled = settings == false
  local auto = settings == true or pandoc.utils.stringify(settings or '') == 'auto'
  local loop = true
  if type(settings) == 'table' and #settings == 0 then
    for _, key in ipairs({'effect', 'desc-position', 'css-class'}) do
      assert(settings[key] == nil, 'Askr image viewer does not support lightbox.' .. key)
    end
    auto = pandoc.utils.stringify(settings.match or '') == 'auto'
    loop = settings.loop ~= false
  end
  doc.meta['askr-viewer-disabled'] = disabled
  doc.meta['askr-viewer-auto'] = auto
  doc.meta['askr-viewer-loop'] = loop
  doc.meta.lightbox = false
  return doc:walk({Image=function(img)
    for _, key in ipairs({'effect', 'desc-position', 'css-class'}) do
      assert(img.attributes[key] == nil, 'Askr image viewer does not support ' .. key .. '.')
    end
    if img.classes:includes('lightbox') then
      img.classes = img.classes:filter(function(c) return c ~= 'lightbox' end)
      img.classes:insert('askr-image-explicit')
    end
    return img
  end})
end
