# How the Work Is Made

## The unit: a lattice path
Every piece is a **path through one of three crystal lattices** — simple cubic (SC),
body-centered cubic (BCC), or face-centered cubic (FCC). Two rules are absolute:

- **Closed** — the path's beginning and end meet. "Open ends are messy; we like closed things."
- **Non-self-intersecting** — the path never crosses itself. "Intersections are dangerous."

A path is a **journey** that should be interesting, built from **motifs**.

## The forms he looks for
Within that closed-path rule, certain families of structure keep recurring: **knots** — the
trefoil, the figure-eight, and others — along with **spirals** and **optical illusions**. Each is
built up from motifs and segments and then developed with symmetry.

## The three lattices
Anton teaches them by asking you to imagine living at the center of a cube:

| Lattice | Directions | Pointing toward |
|---|---|---|
| Simple Cubic (SC) | 6 | the centers of the cube's 6 faces |
| Body-Centered Cubic (BCC) | 8 | the cube's 8 corners |
| Face-Centered Cubic (FCC) | 12 | the midpoints of the cube's 12 edges |

The FCC lattice's **twelve directions** are special to him — they map onto the **twelve notes of
the chromatic scale**.

## The expression language and the solver
Anton built his own **algebraic expression language** to specify the kinds of paths he wants,
together with a **solver** that searches a lattice and finds them. Because a path never doubles
back on itself, the viable directions at each step are one fewer than the totals: 5, 7, or 11. A
single expression can return nothing, a handful of paths, or millions.

## Beauty filters
From those many solutions, Anton curates with a set of **filters** — as his mentor put it, the
artist "gets to play god and decide what's beautiful." They work at several levels:

- **Symmetry.** Score each path against the **48 symmetries of the cube** and rank the highest to
  the top; he favors paths that satisfy many symmetries at once.
- **Knots.** Deciding whether a closed path is knotted is famously hard, so Anton uses an
  ingenious shortcut: take the first three points of the path, which form a small triangle, and
  test whether the rest of the path passes *through* that triangle. If it doesn't, he tightens
  the path and tries again — repeating until the path either reveals a knot or simplifies away. In
  practice it identifies genuine knots remarkably reliably.
- **Rotational symmetry, by eye.** He wraps a path in its **convex hull**, orients it by that
  hull, and looks at the 2-D silhouette for interesting rotational symmetry.
- **Möbius.** He searches specifically for paths whose twisting profile produces a **Möbius**
  surface (see "Giving the path a body," below).

## Drawing a motif
Anton also has a **drawing tool**: he can sketch a motif directly in the lattice — say a
right-angled **zigzag** — and then reference that drawn shape inside an expression, so the engine
generates full paths built around it. One result is a piece he calls a **"fence around nothing,"**
a zigzag enclosing empty space — a name his mentor Koos coined for one of his own designs. Spirals
work the same way: draw a spiral segment, make it a motif, and search for paths that use it.

## Music for the eyes
With FCC's twelve directions mapped to the twelve chromatic notes, Anton composes a **motif** in
his path language and develops it the way a composer would — **repeat, reverse, reflect, scale,
mirror** — variation and inversion. The path ends in **closure**: the journey resolving home, like
resolving to the tonic.

## Polylinear and curved
A path can be executed two ways: **polylinear**, following the straight lattice edges, or
**curved**, by relaxing and interpolating smoothly through the lattice vertices. Anton works in
both; the choice for each piece is a visual judgment.

## Giving the path a body
A path is only a skeleton; to make a sculpture Anton has to give it a **profile** — a
cross-section swept along its length, like putting "meat on the bone." Two elegant geometric
problems come up here:

- **Curved pieces and "developability."** A flat sheet of material can only be bent, without
  stretching or tearing, into a **cylinder** or a **cone** — so a constant cross-section swept
  around a curve usually won't lie flat. Anton's solution is to build a **trapezoidal**
  cross-section that always **points toward the path's center**: its edges then behave partly
  like a cylinder and partly like a cone, so the whole surface stays buildable from sheet
  material.
- **Möbius surfaces.** As a rectangular profile follows a path it can pick up a **twist**.
  Depending on how much, the finished sculpture can have four faces, two, or — in a true
  **Möbius** form — a single continuous face. Anton hunts for these and likes to make the
  topology visible with color: a black-and-white piece where you can see it really has only two
  sides.

## Precision is everything
Because the work *is* symmetry, any flaw in the making is glaring — we notice an off-square corner
the way we'd notice a crooked picture frame, "a thorn in the eye." So execution matters as much as
the idea. Anton designs the forms and partners with fabricators attuned to his standards,
increasingly using **numerically-controlled and robotic** fabrication — including **robotic marble
cutting** — while the final touches, like patina and hand-finishing stone, stay in human hands.

## From file to foundry — and to augmented reality
Anton's forms begin in a computer program he wrote, but they don't all stay virtual: about **a
dozen designs a year** are sent to a foundry and cast in **bronze or steel**. His pieces have been
described as standing in the tradition of modernist sculptors like **Brancusi, Calder, and
Noguchi** — streamlined and sinuous — but more complex, regular, and symmetrical.

The work also lives in **augmented reality**. In partnership with New York's **National Museum of
Mathematics (MoMath)**, Anton's rotating exhibition **"Global Perspective: Math, Art and
Architecture Around the World"** placed virtual sculptures at landmark sites — the Washington
Monument grounds, Times Square, and locations in Paris, Tokyo, and Mexico City — viewable through
a phone's camera. Each month brought a new theme: fractals, optical illusions, Möbius strips,
polylines, knots.

## The method, written down (the Bridges papers)
Anton's process isn't just studio practice — it's documented in a series of peer-reviewed papers
he has co-authored with **Tom Verhoeff** for **Bridges**, the annual conference on mathematics
and art. Together they trace the whole pipeline:

- **"Artistic Rendering of Curves via Lattice Paths" (2017)** — the technique behind the
  **curved** pieces: take a curve, snap it to a lattice, then round it back into a smooth,
  flowing form.
- **"Domain-Specific Languages for Efficient Composition of Paths in 3D" (2023)** — the formal
  description of **Anton's Path Language**, the notation he invented to specify the paths he
  wants. Its syntax looks like file paths with wildcards, and a single expression stands for the
  whole *set* of paths that satisfy it.
- **"Looking for Lovely Links in Lattices" (2024)** — extending the idea from a single path to
  **links** of two or more paths that are genuinely entangled yet fit snugly together. One link
  from this paper, the **"Quartangle,"** was chosen as the **logo of the 2025 Bridges
  conference**. Anton first built a **heuristic link-finder in Grasshopper**; Tom Verhoeff then
  **upgraded it into a rigorous mathematical Python script**, turning Anton's hand-tuned search
  into a general algorithm — a good example of how the two of them work together.
- **"Finding 3D Lattice Paths Exhibiting Knotted Optical Illusions" (2025)** — the search for
  paths whose projections look irreconcilable from different angles, a direct expression of
  Anton's belief in the danger of judging from a single viewpoint.

## The tools behind the work
Anton describes his approach as that of a **non-mathematician** working closely with
mathematicians: he prototypes an idea in his own creative, heuristic way (mostly in **Grasshopper**,
the visual-programming environment for the 3D software Rhinoceros), and then collaborators turn
those prototypes into rigorous tools. **Tom Verhoeff** gave him the very first path-generating
code and later wrote the link-finder; a **software engineer and mathematician Anton has worked with
for over a decade** built the production search engines.

One insight shaped everything. Early on, generating paths by coordinates produced endless
**duplicates** — the same path rotated or reflected into one of the 48 cube symmetries. Anton's
fix was to change how a path is *described*: instead of coordinates, use **relative moves** —
"go forward, turn" — the way you'd steer a turtle in classic "turtle graphics." Because relative
moves don't care which way the whole path is oriented, the duplicates simply never arise. Building
on a paper Tom had written about turtle graphics in three dimensions, that idea became the
**3-D engine** at the heart of the work today.

## Into the plane: tilings and a record to chase
More recently Anton has turned to the **plane**. Encouraged by the Escher scholar **Doris
Schattschneider** — who pointed him to the **Conway criterion** for tiling and to the **28 "Heesch
types,"** the systematic recipes for building interlocking, Escher-like tiles — he developed a
second engine, devoted to **tessellations**. It can tell whether a tile **tiles the plane**, and
generate tiles far more intricate than traditional methods allow.

That opened a genuine mathematical adventure: the hunt for a high **Heesch number**. A tile's
Heesch number is how many complete **rings ("coronas")** of copies you can fit around it before it
gets stuck. The known record is **6**; Anton is chasing a tile that reaches **7**. His strategy is
to generate elaborate tiles, filter out the ones that tile forever (those are no use), and gently
deform promising candidates so they *almost* tile — which is exactly where high Heesch numbers
hide. He finds the tiles beautiful in their own right — pure Escher and Alhambra — so the search
feeds directly back into the art.

## Families of work: Links, Relativity, Duality
Beyond single paths, Anton groups much of his work into a few families — each a different way of
**staging perspective**:

- **Links** — two or more separate, entangled paths. He looks for links that read as **completely
  different objects from one angle** and reveal themselves as **identical, or mirror images, from
  another**; or black-and-white links that look all-black from one side and all-white from the
  other.
- **Relativity** — two lattice paths placed near each other on the lattice grid, where the
  *relationship* between them creates views neither piece has alone.
- **Duality** — a play on "dual" (a structure's mathematical counterpart) and "duo" (two of the
  same) — works that pair complementary or identical forms.
