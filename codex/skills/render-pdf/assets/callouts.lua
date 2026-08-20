-- Lua filter: convert fenced divs to tcolorbox LaTeX environments
-- Supports: ::: warningbox, ::: notebox, ::: dangerbox, ::: tipbox
function Div(el)
  local box_classes = {"warningbox", "notebox", "dangerbox", "tipbox"}
  for _, cls in ipairs(box_classes) do
    if el.classes:includes(cls) then
      local opening = pandoc.RawBlock("latex", "\\begin{" .. cls .. "}")
      local closing = pandoc.RawBlock("latex", "\\end{" .. cls .. "}")
      local blocks = pandoc.List({opening})
      blocks:extend(el.content)
      blocks:insert(closing)
      return blocks
    end
  end
end
