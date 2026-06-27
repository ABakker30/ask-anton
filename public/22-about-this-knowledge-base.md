# About this knowledge base

Ask Anton is a conversational knowledge base about Anton Bakker, his sculpture, and the history
connected to it. You ask a question in plain language, the way you would ask a person, and it answers
and shows the relevant images and documents beside the text.

## What is in it
It holds Anton's body of work (the realized sculptures and the digital designs they grow from), the
exhibitions, the ideas behind the work, the story of his mentor Koos Verhoeff, and archival material
such as the Koos and Escher record (the inscribed *Fish* print, Escher's 1963 lecture texts and
agendas, period documents, and the painted portraits). Every image and document carries a caption, so
the right one can be surfaced and described.

## How it is organized
Under the surface it is built like a wiki. The knowledge lives as a set of focused entries, each on
one subject, the way a wiki has one page per topic: a page for the ideas behind the work, one for
materials, one for the origin and the mentor, one for each major exhibition, one for particular pieces
or series, one for the Koos and Escher record, and so on. Within each page the content is broken into
clearly headed sections, for example "The Mathematical Centre years" or "Chess with Escher." The
images and videos are organized the same way: each is a separate item with a written caption, grouped
under the piece it belongs to, like a labeled card in a catalog. Adding knowledge means writing a new
page or a new section, much like editing a wiki, except every addition is authored and reviewed by
hand before it goes in. Nothing is pulled in automatically from the web.

The difference from a wiki is that you do not browse it. You reach it by asking.

## How a question is answered
When you ask something, the assistant is given the curated written knowledge to work from, and for the
much larger library of pictures and documents it uses meaning-based search to surface the few most
relevant items. A small multilingual model compares the intent of your question against the meaning of
each item, so it understands what you mean rather than just matching keywords, and it works across
languages. Those sources are then handed to an AI model (Claude), which composes a single tailored
answer and chooses which images to show. Every answer is assembled from Anton's own sources rather
than from the model's general memory. This approach is commonly called retrieval-augmented generation.

In use, replies stream in as they are written, relevant images and short videos appear beside the text
with a way to see more, you can ask by voice, images can be opened larger, and the tool offers
follow-up questions.

## Why it works so well
Several things, together:

- **The domain is small and curated.** Everything is about Anton's world and was added on purpose, so
  there is very little noise. A focused, hand-built base is far more accurate than a large scrape,
  where the right answer is buried among contradictions.
- **Answers are grounded in the sources.** The assistant writes from this curated material rather than
  from its general memory, which keeps it close to the facts instead of inventing.
- **Each section is written to stand on its own.** A passage makes sense lifted out of its page, which
  keeps answers precise and makes the base easy to grow, because every piece is a clean, self-contained
  unit.
- **Pictures are found by meaning and carry captions.** Because every image has a clear caption, the
  system can read its way to the right picture and place it beside the words.
- **Provenance is marked.** Sections note when something is firsthand, an oral recollection, or still
  to be confirmed, so answers carry the right level of confidence.

## How it stays accurate
The tool answers only from the curated material. It does not draw on the open internet and it is not
meant to improvise, so it stays close to the sources. Where a fact is an oral recollection or still to
be confirmed, the text says so. It is still software, so if anything looks wrong it can be reported to
Anton and corrected at the source, and that correction loop is part of how the base is kept accurate
and improves over time. For anything you intend to publish, treat it as a fast, sourced guide to
Anton's own records, and confirm against the underlying documents or with Anton, as you would with any
primary-source archive.

## Privacy
You can simply use it. It runs on Anton's own infrastructure, there is no login and no account, and it
asks for nothing personal in order to answer a question. The public side holds no sensitive keys and
can read only the published, curated layer, so anything private is not reachable, and visits are
anonymous, with no IP addresses stored.

## What it is good for
Getting to know the work and the ideas, finding and viewing specific pieces and their images, and
researching the history around them, all by asking rather than searching.
