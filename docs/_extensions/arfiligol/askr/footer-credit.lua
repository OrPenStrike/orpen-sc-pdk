-- Package credit owns only its appended block; native footer content stays authored.
function Pandoc(doc)
  if not quarto.doc.is_format('html:js') then return doc end
  local footer = doc.meta.askr and doc.meta.askr.footer
  if footer and footer.credit == false then return doc end
  local metadata = assert(io.open(pandoc.path.join({pandoc.path.directory(PANDOC_SCRIPT_FILE), '_extension.yml'}), 'r'))
  local version = metadata:read('*a'):match('\nversion:%s*([^%s]+)')
  metadata:close()
  assert(version, 'Askr footer: installed extension metadata has no version.')
  quarto.doc.include_text('after-body', '<template id="askr-footer-credit"><span class="askr-footer-credit">Powered by <a href="https://arfiligol.github.io/askr/">Askr</a><span aria-hidden="true">·</span><a href="https://github.com/arfiligol/askr/releases/tag/v' .. version .. '" aria-label="Askr version ' .. version .. '">' .. version .. '</a></span></template>')
  return doc
end
