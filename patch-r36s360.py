#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
cpp = root / "es-app/src/views/SystemView.cpp"
hdr = root / "es-app/src/views/SystemView.h"

if not cpp.exists() or not hdr.exists():
    raise SystemExit("ERRO: rode este patch dentro da raiz do EmulationStation-fcamod (branch 351v).")

c = cpp.read_text(encoding="utf-8")
h = hdr.read_text(encoding="utf-8")

if "// R36S360_MOSAIC_V01" in c:
    print("Patch R36S360 V0.1 já aplicado.")
    raise SystemExit(0)

needle_h = "\tvoid renderCarousel(const Transform4x4f& trans);\n"
if needle_h not in h:
    raise SystemExit("ERRO: assinatura renderCarousel não encontrada em SystemView.h.")
h = h.replace(
    needle_h,
    needle_h +
    "\tvoid renderR36S360Mosaic(const Transform4x4f& trans);\n"
    "\tvoid moveR36S360MosaicCursor(int dx, int dy);\n",
    1
)

needle_const = "const int logoBuffersRight[] = { 1, 2, 5 };\n"
if needle_const not in c:
    raise SystemExit("ERRO: ponto de inserção de constantes não encontrado.")
c = c.replace(
    needle_const,
    needle_const +
    "\n// R36S360_MOSAIC_V01\n"
    "static const int R36S360_MOSAIC_COLUMNS = 3;\n"
    "static const int R36S360_MOSAIC_ROWS = 3;\n"
    "static const int R36S360_MOSAIC_PAGE_SIZE = R36S360_MOSAIC_COLUMNS * R36S360_MOSAIC_ROWS;\n",
    1
)

needle_input = "\t\tswitch (mCarousel.type)\n"
if needle_input not in c:
    raise SystemExit("ERRO: switch de navegação do SystemView não encontrado.")

mosaic_input = '''\t\t// R36S360 V0.1: grade 3x3 real na tela de sistemas.
\t\tif (config->isMappedLike("left", input))
\t\t{
\t\t\tmoveR36S360MosaicCursor(-1, 0);
\t\t\treturn true;
\t\t}
\t\tif (config->isMappedLike("right", input))
\t\t{
\t\t\tmoveR36S360MosaicCursor(1, 0);
\t\t\treturn true;
\t\t}
\t\tif (config->isMappedLike("up", input))
\t\t{
\t\t\tmoveR36S360MosaicCursor(0, -1);
\t\t\treturn true;
\t\t}
\t\tif (config->isMappedLike("down", input))
\t\t{
\t\t\tmoveR36S360MosaicCursor(0, 1);
\t\t\treturn true;
\t\t}

'''
c = c.replace(needle_input, mosaic_input + needle_input, 1)

start = c.find("void SystemView::render(const Transform4x4f& parentTrans)")
end = c.find("std::vector<HelpPrompt> SystemView::getHelpPrompts()", start)
if start < 0 or end < 0:
    raise SystemExit("ERRO: função render principal não encontrada.")
segment = c[start:end]
if segment.count("renderCarousel(trans);") != 2:
    raise SystemExit("ERRO: quantidade inesperada de renderCarousel no render principal.")
segment = segment.replace("renderCarousel(trans);", "renderR36S360Mosaic(trans);")
c = c[:start] + segment + c[end:]

old_help = '''\tif (mCarousel.type == VERTICAL || mCarousel.type == VERTICAL_WHEEL)
\t\tprompts.push_back(HelpPrompt("up/down", _("CHOOSE")));
\telse
\t\tprompts.push_back(HelpPrompt("left/right", _("CHOOSE")));
'''
new_help = '''\t// R36S360: o mosaico usa os quatro sentidos.
\tprompts.push_back(HelpPrompt("up/down", _("CHOOSE")));
\tprompts.push_back(HelpPrompt("left/right", _("CHOOSE")));
'''
if old_help not in c:
    raise SystemExit("ERRO: bloco de help prompts não encontrado.")
c = c.replace(old_help, new_help, 1)

needle_render = "//  Render system carousel\nvoid SystemView::renderCarousel(const Transform4x4f& trans)\n"
if needle_render not in c:
    raise SystemExit("ERRO: ponto renderCarousel não encontrado.")

mosaic_funcs = r'''// R36S360_MOSAIC_V01
void SystemView::moveR36S360MosaicCursor(int dx, int dy)
{
    if (mEntries.empty())
        return;

    const int size = (int)mEntries.size();
    const int cols = R36S360_MOSAIC_COLUMNS;
    int current = mCursor;
    int row = current / cols;
    int col = current % cols;
    int target = current;

    if (dx < 0)
    {
        if (col > 0)
            target = current - 1;
    }
    else if (dx > 0)
    {
        if (col < cols - 1 && current + 1 < size)
            target = current + 1;
    }
    else if (dy < 0)
    {
        if (row > 0)
            target = current - cols;
    }
    else if (dy > 0)
    {
        if (current + cols < size)
            target = current + cols;
        else
        {
            int last = size - 1;
            if ((last / cols) > row)
                target = last;
        }
    }

    if (target != current)
    {
        listInput(target - current);
        listInput(0);
    }
}

void SystemView::renderR36S360Mosaic(const Transform4x4f& trans)
{
    if (mEntries.empty())
        return;

    const float screenW = mSize.x();
    const float screenH = mSize.y();

    const float marginX = screenW * 0.028f;
    const float top = screenH * 0.155f;
    const float bottom = screenH * 0.105f;
    const float gapX = screenW * 0.0125f;
    const float gapY = screenH * 0.016f;

    const float tileW = (screenW - marginX * 2.0f - gapX * (R36S360_MOSAIC_COLUMNS - 1)) / R36S360_MOSAIC_COLUMNS;
    const float tileH = (screenH - top - bottom - gapY * (R36S360_MOSAIC_ROWS - 1)) / R36S360_MOSAIC_ROWS;

    const int pageStart = (mCursor / R36S360_MOSAIC_PAGE_SIZE) * R36S360_MOSAIC_PAGE_SIZE;
    const int pageEnd = Math::min(pageStart + R36S360_MOSAIC_PAGE_SIZE, (int)mEntries.size());

    Renderer::pushClipRect(
        Vector2i((int)trans.translation().x(), (int)trans.translation().y()),
        Vector2i((int)screenW, (int)screenH));

    for (int index = pageStart; index < pageEnd; index++)
    {
        const int local = index - pageStart;
        const int row = local / R36S360_MOSAIC_COLUMNS;
        const int col = local % R36S360_MOSAIC_COLUMNS;

        const float x = marginX + col * (tileW + gapX);
        const float y = top + row * (tileH + gapY);
        const bool selected = index == mCursor;

        Renderer::setMatrix(trans);

        const unsigned int bg = selected ? 0x5E941CFF : 0x494949E8;
        const unsigned int bgEnd = selected ? 0x78B82AFF : 0x626262E8;
        Renderer::drawRect(x, y, tileW, tileH, bg, bgEnd, true);

        if (selected)
        {
            const float b = 2.0f;
            const unsigned int edge = 0xD8F0B8FF;
            Renderer::drawRect(x, y, tileW, b, edge, edge, true);
            Renderer::drawRect(x, y + tileH - b, tileW, b, edge, edge, true);
            Renderer::drawRect(x, y, b, tileH, edge, edge, true);
            Renderer::drawRect(x + tileW - b, y, b, tileH, edge, edge, true);
        }

        const std::shared_ptr<GuiComponent>& comp = mEntries.at(index).data.logo;
        if (comp)
        {
            comp->setScale(selected ? 0.78f : 0.68f);
            comp->setOpacity(selected ? 0xFF : 0xD8);
            comp->setRotationDegrees(0);

            Transform4x4f logoTrans = trans;
            const float logoX = x + (tileW - mCarousel.logoSize.x()) * 0.5f;
            const float logoY = y + (tileH - mCarousel.logoSize.y()) * 0.5f;
            logoTrans.translate(Vector3f(logoX, logoY, 0.0f));
            comp->render(logoTrans);
        }
    }

    Renderer::popClipRect();
}

'''
c = c.replace(needle_render, mosaic_funcs + needle_render, 1)

hdr.write_text(h, encoding="utf-8")
cpp.write_text(c, encoding="utf-8")

print("Patch R36S360 Frontend V0.1 aplicado com sucesso.")
