# ui-ux-analytical-dashboard.skill.md

A reusable **UI/UX skill file** for designing calm, high-signal, analytical dashboards  
(finance, data science, dev tools, internal platforms).

This file captures **principles, rules, and checks** that can be applied repeatedly and mechanically.

---

## Skill: Analytical UI / UX Design

### Goal
Design interfaces that:
- Answer the user’s core question immediately
- Scale from novice to expert
- Minimize cognitive and emotional load
- Prioritize clarity, trust, and rational decision-making

---

## 1. Core Question First

**Rule:**  
The primary user question must be answered in under **1 second**.

**Checks**
- [ ] Is the most important metric visually dominant?
- [ ] Can the user understand the current state without interaction?
- [ ] Is the “so what?” obvious at first glance?

---

## 2. Progressive Disclosure

**Rule:**  
Reveal complexity only as the user asks for it.

**Structure**
1. Summary (what’s happening)
2. Breakdown (why)
3. Detail (exact data)

**Checks**
- [ ] High-level info appears first
- [ ] Details are optional, not mandatory
- [ ] No critical info is hidden behind interaction

---

## 3. Visual Hierarchy via Typography

**Rule:**  
Typography is the primary layout and hierarchy mechanism.

**Guidelines**
- Size → importance  
- Weight → emphasis  
- Alignment → structure  
- Spacing → grouping  

**Checks**
- [ ] If borders/cards are removed, does hierarchy remain clear?
- [ ] Are font sizes limited and intentional?
- [ ] Are labels visually subordinate to values?

---

## 4. Semantic Color Usage

**Rule:**  
Color encodes **meaning**, never decoration.

**Conventions**
- Green / red → positive / negative state only
- Neutral colors → structure, trends, context
- No color without semantic purpose

**Checks**
- [ ] Does the UI work in grayscale?
- [ ] Is color never the sole carrier of information?
- [ ] Are gains/losses the only emotionally coded elements?

---

## 5. Charts vs Tables

**Rule:**  
Match the visualization to the cognitive task.

**Usage**
- Charts → trends, direction, momentum
- Tables → precision, comparison, inspection

**Checks**
- [ ] Charts avoid unnecessary precision
- [ ] Tables show exact values clearly
- [ ] No chart tries to do a table’s job

---

## 6. Noise Reduction

**Rule:**  
Remove everything that does not directly support understanding.

**Guidelines**
- Minimal gridlines
- Minimal labels
- No decorative gradients or shadows

**Checks**
- [ ] Every visual element justifies its existence
- [ ] Removing an element would reduce clarity

---

## 7. Accurate Data Encoding

**Rule:**  
Use perceptually accurate encodings.

**Priority Order**
1. Position / length  
2. Alignment  
3. Area  
4. Color  
5. Shape  

**Checks**
- [ ] Proportions use length, not angles
- [ ] Pie charts avoided unless trivial
- [ ] Visuals exactly match numeric values

---

## 8. Scanability

**Rule:**  
Design for eyes in motion, not careful reading.

**Guidelines**
- Align numbers consistently
- Chunk related information
- Avoid dense paragraphs

**Checks**
- [ ] Rows can be scanned vertically
- [ ] Important values stand out without reading labels
- [ ] Layout supports diagonal scanning

---

## 9. Tables & Dense Views

**Rule:**  
High density, low friction.

**Guidelines**
- Numbers right-aligned, text left-aligned
- Subtle row separation
- Expansion instead of clutter

**Checks**
- [ ] Tables are readable at a glance
- [ ] Secondary details are hidden, not removed
- [ ] Sorting and scanning are fast

---

## 10. Interaction & Defaults

**Rule:**  
Defaults shape behavior; choose them carefully.

**Checks**
- [ ] Default time range is sensible
- [ ] Current state is always obvious
- [ ] No surprising interactions
- [ ] Controls behave consistently everywhere

---

## 11. Time & Context

**Rule:**  
Provide context without forcing comparison.

**Checks**
- [ ] Time horizon supports good judgment
- [ ] Historical context is available but secondary
- [ ] Timestamps are visible but unobtrusive

---

## 12. Comparison & Benchmarks

**Rule:**  
Comparison is optional, not imposed.

**Checks**
- [ ] Benchmarks are visually subordinate
- [ ] Comparisons do not dominate the primary narrative
- [ ] UI avoids anchoring or performance shaming

---

## 13. Cognitive Load Management

**Rule:**  
Reduce thinking required to understand structure.

**Checks**
- [ ] Fewer than ~7 distinct visual concepts on screen
- [ ] Repeated patterns are reused, not reinvented
- [ ] Interface is understandable without explanation

---

## 14. Emotional Regulation

**Rule:**  
Serious tools must be calm.

**Guidelines**
- No gamification
- No celebration or alarm visuals
- Neutral language

**Checks**
- [ ] UI does not amplify emotion
- [ ] Gains and losses are presented factually
- [ ] Interface feels stable and trustworthy

---

## 15. Consistency & Learnability

**Rule:**  
Once learned, everything should feel predictable.

**Checks**
- [ ] Same actions behave the same everywhere
- [ ] Icons and colors are reused consistently
- [ ] New sections feel familiar immediately

---

## 16. Expert Scaling

**Rule:**  
The same UI must work for novices and experts.

**Checks**
- [ ] Power users can move quickly
- [ ] Detail is accessible without modal friction
- [ ] Depth comes from structure, not modes

---

## 17. Accessibility & Robustness

**Checks**
- [ ] Sufficient contrast everywhere
- [ ] Color-blind safe
- [ ] Readable at different zoom levels

---

## Final Sanity Test

Ask yourself:
- Would I trust this UI with real money or decisions?
- Does anything exist purely “because it looks nice”?
- Does the interface get out of the way?

**Golden Rule:**  
> If users notice the interface, it’s failing.

---

End of skill file.
