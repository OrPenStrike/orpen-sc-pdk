-- Register rendered figures after Quarto resolves their paths and IDs. Only Askr
-- supplies interaction; these links remain useful when JavaScript is disabled.
local function text(v) return v and pandoc.utils.stringify(v) or nil end
local function escape(v)
  return v:gsub('&', '&amp;'):gsub('<', '&lt;'):gsub('>', '&gt;'):gsub('"', '&quot;')
end
local function has(el, class) return el.classes and el.classes:includes(class) end
local function fail(message) assert(false, message) end

function Pandoc(doc)
  if not quarto.doc.is_format('html:js') then return doc end
  local logout = doc.meta.askr and doc.meta.askr.logout
  if logout ~= nil then
    if type(logout) ~= 'table' or logout.t == 'MetaInlines' then
      fail('askr.logout: use a mapping with href and optional label.')
    end
    local href, label = text(logout.href), text(logout.label) or 'Logout'
    if not href or href == '' or href:find('[%s%c\\]') or
       not (href:match('^https://[^/?#]+') or (href:sub(1,1) == '/' and href:sub(2,2) ~= '/')) then
      fail('askr.logout.href: expected an HTTPS URL or a domain-root /path, not //host.')
    end
    if label == '' then fail('askr.logout.label: must not be empty.') end
    quarto.doc.include_text('after-body', '<template id="askr-logout-config"><a class="askr-logout" href="' ..
      escape(href) .. '" aria-label="' .. escape(label) .. '" title="' .. escape(label) ..
      '"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg></a></template>')
  end

  local disabled = doc.meta['askr-viewer-disabled'] == true
  local auto = doc.meta['askr-viewer-auto'] == true
  quarto.doc.include_text('after-body', '<template id="askr-viewer-config" data-loop="' ..
    tostring(doc.meta['askr-viewer-loop'] ~= false) .. '"></template>')
  local entry_serial = 0
  local function wrap(img, automatic, gallery)
    if disabled or has(img, 'nolightbox') then return nil end
    if not (automatic and auto or has(img, 'askr-image-explicit') or has(img, 'lightbox')) then return nil end
    entry_serial = entry_serial + 1
    local attrs = {['data-askr-image-key']=tostring(entry_serial),
      ['data-askr-gallery']=img.attributes.group or gallery or '',
      ['data-askr-description']=img.attributes.description or ''}
    return pandoc.Link({img}, img.src, pandoc.utils.stringify(img.caption),
      pandoc.Attr('', {'askr-image-entry'}, attrs))
  end
  doc = doc:walk({traverse='topdown',
    Link=function() return nil, false end,
    Div=function(div)
      if has(div, 'quarto-figure') then
        local images = 0
        div:walk({Image=function() images = images + 1 end})
        local gallery = images > 1 and div.identifier ~= '' and div.identifier or nil
        return div:walk({traverse='topdown', Link=function() return nil,false end,
          Image=function(img) return wrap(img,true,gallery),false end}), false
      end
      if has(div, 'cell') and div.attributes.lightbox then
        local options = quarto.json.decode(div.attributes.lightbox)
        local number = 0
        div = div:walk({Image=function(img)
          number = number + 1
          if options == false or type(options) == 'table' and options.nolightbox then
            img.classes:insert('nolightbox')
          elseif options == true or type(options) == 'table' then
            img.classes:insert('askr-image-explicit')
            if type(options) == 'table' then
              for _, key in ipairs({'effect', 'desc-position', 'css-class'}) do
                assert(options[key] == nil, 'Askr image viewer does not support ' .. key .. '.')
              end
              if options.group then img.attributes.group = options.group end
              if type(options.description) == 'string' then img.attributes.description = options.description
              elseif type(options.description) == 'table' and options.description[number] then img.attributes.description = options.description[number] end
            end
          end
          return img
        end})
      end
      return div
    end,
    Para=function(para)
      if #para.content == 1 and para.content[1].t == 'Image' then
        local entry = wrap(para.content[1], true)
        if entry then return pandoc.Para({entry}), false end
      end
    end,
    Plain=function(para)
      if #para.content == 1 and para.content[1].t == 'Image' then
        local entry = wrap(para.content[1], true)
        if entry then return pandoc.Plain({entry}), false end
      end
    end,
    Image=function(img) return wrap(img, false), false end
  })
  local eligible, identities = {}, {}
  doc:walk({Link=function(link)
    if has(link, 'askr-image-entry') then
      link:walk({Image=function(img)
        if img.identifier ~= '' then
          eligible[img.identifier] = img.src
          identities[img.identifier] = link.attributes['data-askr-image-key']
        end
      end})
    end
  end, Div=function(div)
    if div.identifier == '' then return end
    local count = 0
    div:walk({Link=function(link) if has(link, 'askr-image-entry') then count = count + 1 end end})
    if count == 1 then
      div:walk({Link=function(link)
        if has(link, 'askr-image-entry') then
          eligible[div.identifier] = link.target
          identities[div.identifier] = link.attributes['data-askr-image-key']
        end
      end})
    end
  end})
  local inline_targets, inline_seen = {}, {}
  local function button(el)
    if not has(el, 'askr-image-button-entry') then return nil end
    local target = el.attributes['data-askr-image-target']
    if disabled then
      fail('askr-image-view: lightbox: false conflicts with an image-view button.')
    end
    if not eligible[target] then
      fail('askr-image-view: target "' .. target .. '" must identify one eligible image (not linked, inline prose, or .nolightbox).')
    end
    local label = pandoc.utils.stringify(el.content)
    if el.attributes['data-askr-image-mode'] == 'inline' then
      assert(not inline_seen[identities[target]], 'askr-image-view: duplicate inline target "' .. target .. '".')
      inline_seen[identities[target]] = true
      inline_targets[target] = true
      return pandoc.RawBlock('html', '<span class="askr-inline-request" data-askr-image-target="' ..
        escape(target) .. '" data-label="' .. escape(label) .. '" hidden></span>')
    end
    local html = '<a class="askr-image-view" data-askr-image-target="' ..
      escape(target) .. '" href="' .. escape(eligible[target]) .. '" aria-haspopup="dialog">' .. escape(label) .. '</a>'
    if el.t == 'Span' then return pandoc.RawInline('html', html) end
    return pandoc.RawBlock('html', html)
  end
  doc = doc:walk({Div=button, Span=button})
  return doc:walk({Div=function(div)
    if has(div, 'askr-image-source') then
      local is_inline = false
      div:walk({Image=function(img) if inline_targets[img.identifier] then is_inline = true end end})
      if is_inline then
        div.classes:insert('askr-image-source-inline')
        div.attributes['aria-hidden'] = nil
      end
    end
    return div
  end})
end
