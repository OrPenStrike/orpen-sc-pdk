-- Validate entries after Quarto renders its native Lightbox anchors and figure IDs.
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

  local eligible = {}
  doc:walk({Link=function(link)
    if has(link, 'lightbox') then
      link:walk({Image=function(img)
        if img.identifier ~= '' then eligible[img.identifier] = true end
      end})
    end
  end, Div=function(div)
    if div.identifier == '' then return end
    local count = 0
    div:walk({Link=function(link) if has(link, 'lightbox') then count = count + 1 end end})
    if count == 1 then eligible[div.identifier] = true end
  end})
  local function button(el)
    if not has(el, 'askr-image-button-entry') then return nil end
    local target = el.attributes['data-askr-image-target']
    if doc.meta.lightbox == false then
      fail('askr-image-view: lightbox: false conflicts with an image-view button.')
    end
    if not eligible[target] then
      fail('askr-image-view: target "' .. target .. '" must identify an existing, standalone Lightbox image (not linked, inline, or .nolightbox).')
    end
    local label = pandoc.utils.stringify(el.content)
    local html = '<button type="button" class="askr-image-view" data-askr-image-target="' ..
      escape(target) .. '" aria-haspopup="dialog">' .. escape(label) .. '</button>'
    if el.t == 'Span' then return pandoc.RawInline('html', html) end
    return pandoc.RawBlock('html', html)
  end
  return doc:walk({Div=button, Span=button})
end
