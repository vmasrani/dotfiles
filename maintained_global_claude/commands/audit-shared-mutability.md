---
description: Audit Rust code for reflexive (non-intentional) uses of Rc<RefCell>, Arc<Mutex>, and similar shared interior-mutability wrappers
---

Scan the Rust code at `$ARGUMENTS` (default: the current crate) for shared interior-mutability wrappers and classify each occurrence as **intentional**, **smelly**, or **ambiguous**. This is a read-only audit — do not modify code.

## What to find

Use ripgrep to locate occurrences of:

- `Rc<RefCell<...>>`
- `Rc<Cell<...>>`
- `Arc<Mutex<...>>`
- `Arc<RwLock<...>>`
- Type aliases that wrap any of the above (e.g. `type Shared<T> = Rc<RefCell<T>>;` — search for `Rc<` and `Arc<` in type alias position too)

For each hit, read the surrounding function, the enclosing struct, and the call sites that borrow from it. Local context determines classification far more than the line itself.

## Classification

A use is **intentional** when at least one of these holds:

- Models a genuinely cyclic or multi-owner data structure: graphs, DAGs, trees with parent pointers, doubly-linked lists.
- Multiple independent code paths need shared mutable access: observer/pub-sub, plugin registries, GUI widget trees, event-loop handlers, callback registries.
- The value is held across `.await` points or stored in a future where transferring ownership would distort the design.
- For `Arc<Mutex<T>>` / `Arc<RwLock<T>>`: real cross-thread sharing where channels / message passing would be a worse fit.
- It holds trait objects or closures whose ownership is genuinely shared across subsystems.

A use is **smelly** when at least one of these holds:

- The wrapper is a field on a struct that also owns the only mutator — `&mut self` would suffice.
- The interior is mutated from a single call site within one ownership chain.
- The borrow is taken and released inside one function and never escapes.
- The wrapped data is `Copy` or small — `Cell<T>` would be cleaner than `RefCell<T>`.
- It models a graph that could be expressed with indices into an arena, `Vec`, or `SlotMap`.
- It appears in a **public library API** where it leaks an implementation detail and constrains callers (e.g. forces single-threaded use, or imposes locking on consumers who don't need it).
- The same wrapped type appears across many unrelated structs (suggests it should be passed by reference rather than co-owned).
- It's in a hot path where atomic refcount traffic or runtime borrow-check overhead measurably matters.

Mark as **ambiguous** when intent isn't determinable from local context. State what additional information would resolve it (e.g. "need to see how `EventBus` is used outside this module").

## Output

For each finding:

```
[INTENTIONAL | SMELLY | AMBIGUOUS]  path/file.rs:LINE
  Wrapper:   Rc<RefCell<Foo>>
  Context:   <one line: which struct/function, what the data represents>
  Reasoning: <why this classification — cite the specific heuristic>
  Refactor:  <only if smelly — concrete alternative: &mut self threading, arena + index, Cell<T>, channel, restructured ownership, etc.>
```

End the report with:

1. Count per category.
2. Top 3 smelly findings ranked by (impact × ease of refactor) with a one-paragraph plan for each.
3. Cross-cutting patterns — e.g. "5 different structs hold `Rc<RefCell<Config>>`; the config likely belongs in a parent struct and should be passed by `&` or `&mut` reference."

## Don't

- Flag every occurrence as smelly. Many uses are legitimate and refactoring them produces worse code.
- Recommend `unsafe` as an alternative.
- Modify code — this command audits only.
- Propose sweeping API changes without flagging the migration cost.
- Suggest `Arc<Mutex<T>>` → channel rewrites without confirming the access pattern actually fits message passing.
