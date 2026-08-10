const stage = document.querySelector('#stage');
const drawing = document.querySelector('#drawing');
const select = document.querySelector('#layout');
let scale = 1, x = 0, y = 0, drag;

function render() {
  drawing.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
}
function reset() { scale = 1; x = 0; y = 0; render(); }
function load() {
  drawing.src = `../_static/images/components/${select.value}`;
  drawing.alt = select.options[select.selectedIndex].text;
  reset();
}

select.addEventListener('change', load);
document.querySelector('#reset').addEventListener('click', reset);
stage.addEventListener('wheel', event => {
  event.preventDefault();
  const rect = stage.getBoundingClientRect();
  const px = event.clientX - rect.left, py = event.clientY - rect.top;
  const next = Math.min(12, Math.max(.5, scale * Math.exp(-event.deltaY * .001)));
  x = px - (px - x) * next / scale;
  y = py - (py - y) * next / scale;
  scale = next;
  render();
}, { passive: false });
stage.addEventListener('pointerdown', event => {
  drag = { id: event.pointerId, x: event.clientX - x, y: event.clientY - y };
  stage.setPointerCapture(event.pointerId);
});
stage.addEventListener('pointermove', event => {
  if (!drag || drag.id !== event.pointerId) return;
  x = event.clientX - drag.x; y = event.clientY - drag.y; render();
});
stage.addEventListener('pointerup', () => { drag = undefined; });
load();
