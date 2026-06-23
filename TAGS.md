# Tag Vocabulary — single source of truth

Both `doc_handler.py` (validation) and the injected LLM system prompt read THIS file.
Edit a list here and the change flows to the script and the model — no other edits.
Format: inside each ```tags block, first whitespace token = the code; rest = description.

## STREAMS
```tags
CW    coursework / college degree material (B.Tech notes, assignments, lab)
GATE  GATE / competitive-exam prep — PYQs, test series, GATE-specific notes/formula books
PROJ  project deliverable — hardware/software build, capstone, prototype, project report
RES   research — papers, thesis, conference, datasets, literature review
REC   records / admin — marksheet, admit card, certificate, ID, exam form, fee receipt
REF   general reference — textbooks, standards, datasheets not tied to one course
```

## SUBJECTS
```tags
00MM   Math Methods — linear algebra, calculus, probability, transforms, numerical
01CA   Circuit Analysis — KCL/KVL, network theorems, RLC, two-port, transients
02SEMI Semiconductor Physics — carriers, bands, doping, drift/diffusion
03PN   PN Junction / Diodes — depletion, rectifier, zener
04BJT  BJT — bipolar biasing, CE/CB/CC, h-params
05MOS  MOSFET — CMOS, MOS cap, threshold, channel
06OPAMP Op-Amp — inverting, integrator, comparator, feedback
07ANLG Analog Circuits — amplifiers, oscillators, filters, LIC
08DIG  Digital / VLSI / Embedded — logic, FF, counters, verilog, microprocessor, ARM, FPGA
09SNS  Signals & Systems / DSP — fourier, laplace, z-transform, convolution, sampling
10CTRL Control Systems — transfer fn, bode, root locus, state space, stability
11COMM Communications / Networks — modulation, digital comm, info theory, antenna, radar
12EMAG Electromagnetics — maxwell, transmission line, waveguide, fields, smith chart
13TOOLS Programming / CAD / Tools — C/C++/python/matlab, kicad, simulation, lab software
90HUM  Humanities / Management / General — english, constitution, behaviour, management
NA     no single subject (use for PROJ/RES/REC/REF)
99UNS  unsure / multi-subject
```

## TYPES
```tags
notes
pyq
book
slides
assignment
lab
report
datasheet
syllabus
solution
misc
```

## FACETS (Obsidian tags applied later — NOT in the filename prefix)
```facets
source: #remarkable #scanned #handwritten #web
phase:  #sem1 #sem2 #sem3 #sem4 #sem5 #sem6 #sem7 #sem8 #masters #school
```
