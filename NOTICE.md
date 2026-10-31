# Third-party notices

The components below are bundled with clark. Each keeps its own licence, which applies to that component and not to clark's own code. clark's own code is covered by the file `LICENSE` (copyright the clark project, 3101 Park Blvd, Palo Alto, CA 94306, USA); questions about it go to the contact in that file. The licence texts are repeated in full in the second part of this file, because most of them say the notice must travel with the code.

How this list was made: from `vendor/manifest.json`, `vendor/preact/manifest.json`, `vendor/tiptap/manifest.json`, the two font manifests, and the code itself (the Settings gear). The licence text of every npm and PyPI component was compared byte for byte with the file inside the component's own published package (the npm tarball or the PyPI source package named in the manifests). The two fonts are copies of the Google Fonts licence files with two small differences, listed at the end.

Not shipped, so not listed as bundled: esbuild (MIT), the tool that builds the page and the editor. It is downloaded onto a developer's machine and checked against a pinned SHA-256; none of its code is in clark.

## Part 1: the components


### Python libraries

| Component | Version | Licence | Copyright | Where | Licence text |
|---|---|---|---|---|---|
| openpyxl | 3.1.5 | MIT | 2010 openpyxl | vendor/openpyxl/ | [L1](#l1) |
| et_xmlfile | 2.0.0 | MIT | 2010 openpyxl | vendor/et_xmlfile/ | [L1](#l1) |
| et_xmlfile (parts taken from the Python standard library) | 2.0.0 | PSF-2.0 (Python licence) | 2001-present Python Software Foundation; All Rights Reserved | vendor/et_xmlfile/ | [L2](#l2) |

### Page libraries

| Component | Version | Licence | Copyright | Where | Licence text |
|---|---|---|---|---|---|
| preact | 10.29.8 | MIT | 2015-present Jason Miller | vendor/preact/preact/ | [L3](#l3) |
| @preact/signals | 2.11.2 | MIT | 2022-present Preact Team | vendor/preact/signals/ | [L4](#l4) |
| @preact/signals-core | 1.14.4 | MIT | 2022-present Preact Team | vendor/preact/signals-core/ | [L4](#l4) |

### Editor (Tiptap, built into one file)

| Component | Version | Licence | Copyright | Where | Licence text |
|---|---|---|---|---|---|
| @tiptap/core | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-core-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-blockquote | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-blockquote-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-bold | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-bold-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-code | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-code-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-code-block | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-code-block-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-document | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-document-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-hard-break | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-hard-break-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-heading | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-heading-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-horizontal-rule | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-horizontal-rule-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-image | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-image-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-italic | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-italic-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-link | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-link-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-list | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-list-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-paragraph | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-paragraph-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-strike | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-strike-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-table | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-table-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-text | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-text-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extension-underline | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extension-underline-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/extensions | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-extensions-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/markdown | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-markdown-3.31.3-LICENSE.md | [L5](#l5) |
| @tiptap/pm | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-pm-3.31.3-LICENSE | [L5](#l5) |
| @tiptap/pm (third-party list) | 3.31.3 | MIT | Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-pm-3.31.3-THIRD_PARTY_LICENSES.md | [L6](#l6) |
| @tiptap/starter-kit | 3.31.3 | MIT | 2025, Tiptap GmbH | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/tiptap-starter-kit-3.31.3-LICENSE.md | [L5](#l5) |
| linkifyjs | 4.3.3 | MIT | 2024 Nick Frasser | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/linkifyjs-4.3.3-LICENSE | [L7](#l7) |
| marked | 17.0.6 | MIT | 2018+, MarkedJS | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/marked-17.0.6-LICENSE.md | [L8](#l8) |
| orderedmap | 2.1.1 | MIT | 2016 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/orderedmap-2.1.1-LICENSE | [L9](#l9) |
| prosemirror-commands | 1.7.2 | MIT | 2015-2017 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/prosemirror-commands-1.7.2-LICENSE | [L10](#l10) |
| prosemirror-dropcursor | 1.8.4 | MIT | 2015-2017 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/prosemirror-dropcursor-1.8.4-LICENSE | [L10](#l10) |
| prosemirror-gapcursor | 1.4.1 | MIT | 2015-2017 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/prosemirror-gapcursor-1.4.1-LICENSE | [L10](#l10) |
| prosemirror-history | 1.5.0 | MIT | 2015-2017 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/prosemirror-history-1.5.0-LICENSE | [L10](#l10) |
| prosemirror-keymap | 1.2.3 | MIT | 2015-2017 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/prosemirror-keymap-1.2.3-LICENSE | [L10](#l10) |
| prosemirror-model | 1.25.12 | MIT | 2015-2017 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/prosemirror-model-1.25.12-LICENSE | [L10](#l10) |
| prosemirror-schema-list | 1.5.1 | MIT | 2015-2017 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/prosemirror-schema-list-1.5.1-LICENSE | [L10](#l10) |
| prosemirror-state | 1.4.4 | MIT | 2015-2017 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/prosemirror-state-1.4.4-LICENSE | [L10](#l10) |
| prosemirror-tables | 1.8.5 | MIT | 2015-2016 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/prosemirror-tables-1.8.5-LICENSE | [L11](#l11) |
| prosemirror-transform | 1.12.2 | MIT | 2015-2017 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/prosemirror-transform-1.12.2-LICENSE | [L10](#l10) |
| prosemirror-view | 1.42.6 | MIT | 2015-2017 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/prosemirror-view-1.42.6-LICENSE | [L10](#l10) |
| rope-sequence | 1.3.4 | MIT | 2016 by Marijn Haverbeke | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/rope-sequence-1.3.4-LICENSE | [L12](#l12) |
| w3c-keyname | 2.2.8 | MIT | 2016 by Marijn Haverbeke and others | vendor/tiptap/tiptap.module.js; licence file vendor/tiptap/licenses/w3c-keyname-2.2.8-LICENSE | [L9](#l9) |

### Fonts

| Component | Version | Licence | Copyright | Where | Licence text |
|---|---|---|---|---|---|
| Inter | Google Fonts, 30-10-2026 | SIL Open Font License 1.1 | 2020 The Inter Project Authors | vendor/fonts/inter/ | [L13](#l13) |
| Montserrat | Google Fonts, 30-10-2026 | SIL Open Font License 1.1 | 2024 The Montserrat.Git Project Authors | vendor/fonts/montserrat/ | [L14](#l14) |

### Icons

| Component | Version | Licence | Copyright | Where | Licence text |
|---|---|---|---|---|---|
| Feather (the Settings gear shape) | settings.svg, as in the current upstream file | MIT | 2013-2023 Cole Bemis | system/prototype/core.js (the gear icon path) | [L15](#l15) |
| Lucide (credited; carries Feather's MIT notice) | licence file of the current upstream repository | ISC, with Feather's MIT notice | 2026 Lucide Icons and Contributors | system/prototype/core.js (the gear icon, credited in the README) | [L16](#l16) |

Notes:

- **openpyxl**: Excel export and import.
- **et_xmlfile**: Its own MIT licence file (LICENCE.rst in the upstream source package; it is not copied into vendor/licenses/).
- **et_xmlfile (parts taken from the Python standard library)**: et_xmlfile's LICENCE.python, which also carries et_xmlfile's own notes on what it changed.
- **preact**: Draws the page.
- **Inter**: Latin subset, woff2.
- **Montserrat**: Latin subset, woff2.
- **Feather (the Settings gear shape)**: The path is byte-identical to Feather's settings.svg.
- **Lucide (credited; carries Feather's MIT notice)**: Lucide's own settings icon today is drawn differently; clark credits Lucide because the shape came with its Feather lineage. Kept as a precaution.

## Part 2: the licence texts

Each text below is reproduced exactly as it appears in the file named in Part 1. Where several components share the same text, it is given once, with the components it applies to listed above it.


<a id="l1"></a>
### L1: MIT

Applies to: et_xmlfile 2.0.0; openpyxl 3.1.5.

~~~~text
This software is under the MIT Licence
======================================

Copyright (c) 2010 openpyxl

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
~~~~

<a id="l2"></a>
### L2: PSF-2.0 (Python licence)

Applies to: et_xmlfile (parts taken from the Python standard library) 2.0.0.

~~~~text
et_xml is licensed under the MIT license; see the file LICENCE for details.

et_xml includes code from the Python standard library, which is licensed under
the Python license, a permissive open source license. The copyright and license
is included below for compliance with Python's terms.

This module includes corrections and new features as follows:
- Correct handling of attributes namespaces when a default namespace
  has been registered.
- Records the namespaces for an Element during parsing and utilises them to
  allow inspection of namespaces at specific elements in the xml tree and
  during serialisation.

Misc:
- Includes the test_xml_etree with small modifications for testing the
  modifications in this package.

----------------------------------------------------------------------

Copyright (c) 2001-present Python Software Foundation; All Rights Reserved

A. HISTORY OF THE SOFTWARE
==========================

Python was created in the early 1990s by Guido van Rossum at Stichting
Mathematisch Centrum (CWI, see https://www.cwi.nl) in the Netherlands
as a successor of a language called ABC.  Guido remains Python's
principal author, although it includes many contributions from others.

In 1995, Guido continued his work on Python at the Corporation for
National Research Initiatives (CNRI, see https://www.cnri.reston.va.us)
in Reston, Virginia where he released several versions of the
software.

In May 2000, Guido and the Python core development team moved to
BeOpen.com to form the BeOpen PythonLabs team.  In October of the same
year, the PythonLabs team moved to Digital Creations, which became
Zope Corporation.  In 2001, the Python Software Foundation (PSF, see
https://www.python.org/psf/) was formed, a non-profit organization
created specifically to own Python-related Intellectual Property.
Zope Corporation was a sponsoring member of the PSF.

All Python releases are Open Source (see https://opensource.org for
the Open Source Definition).  Historically, most, but not all, Python
releases have also been GPL-compatible; the table below summarizes
the various releases.

    Release         Derived     Year        Owner       GPL-
                    from                                compatible? (1)

    0.9.0 thru 1.2              1991-1995   CWI         yes
    1.3 thru 1.5.2  1.2         1995-1999   CNRI        yes
    1.6             1.5.2       2000        CNRI        no
    2.0             1.6         2000        BeOpen.com  no
    1.6.1           1.6         2001        CNRI        yes (2)
    2.1             2.0+1.6.1   2001        PSF         no
    2.0.1           2.0+1.6.1   2001        PSF         yes
    2.1.1           2.1+2.0.1   2001        PSF         yes
    2.1.2           2.1.1       2002        PSF         yes
    2.1.3           2.1.2       2002        PSF         yes
    2.2 and above   2.1.1       2001-now    PSF         yes

Footnotes:

(1) GPL-compatible doesn't mean that we're distributing Python under
    the GPL.  All Python licenses, unlike the GPL, let you distribute
    a modified version without making your changes open source.  The
    GPL-compatible licenses make it possible to combine Python with
    other software that is released under the GPL; the others don't.

(2) According to Richard Stallman, 1.6.1 is not GPL-compatible,
    because its license has a choice of law clause.  According to
    CNRI, however, Stallman's lawyer has told CNRI's lawyer that 1.6.1
    is "not incompatible" with the GPL.

Thanks to the many outside volunteers who have worked under Guido's
direction to make these releases possible.


B. TERMS AND CONDITIONS FOR ACCESSING OR OTHERWISE USING PYTHON
===============================================================

Python software and documentation are licensed under the
Python Software Foundation License Version 2.

Starting with Python 3.8.6, examples, recipes, and other code in
the documentation are dual licensed under the PSF License Version 2
and the Zero-Clause BSD license.

Some software incorporated into Python is under different licenses.
The licenses are listed with code falling under that license.


PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
--------------------------------------------

1. This LICENSE AGREEMENT is between the Python Software Foundation
("PSF"), and the Individual or Organization ("Licensee") accessing and
otherwise using this software ("Python") in source or binary form and
its associated documentation.

2. Subject to the terms and conditions of this License Agreement, PSF hereby
grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce,
analyze, test, perform and/or display publicly, prepare derivative works,
distribute, and otherwise use Python alone or in any derivative version,
provided, however, that PSF's License Agreement and PSF's notice of copyright,
i.e., "Copyright (c) 2001-2024 Python Software Foundation; All Rights Reserved"
are retained in Python alone or in any derivative version prepared by Licensee.

3. In the event Licensee prepares a derivative work that is based on
or incorporates Python or any part thereof, and wants to make
the derivative work available to others as provided herein, then
Licensee hereby agrees to include in any such work a brief summary of
the changes made to Python.

4. PSF is making Python available to Licensee on an "AS IS"
basis.  PSF MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, PSF MAKES NO AND
DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON WILL NOT
INFRINGE ANY THIRD PARTY RIGHTS.

5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON,
OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.

6. This License Agreement will automatically terminate upon a material
breach of its terms and conditions.

7. Nothing in this License Agreement shall be deemed to create any
relationship of agency, partnership, or joint venture between PSF and
Licensee.  This License Agreement does not grant permission to use PSF
trademarks or trade name in a trademark sense to endorse or promote
products or services of Licensee, or any third party.

8. By copying, installing or otherwise using Python, Licensee
agrees to be bound by the terms and conditions of this License
Agreement.


BEOPEN.COM LICENSE AGREEMENT FOR PYTHON 2.0
-------------------------------------------

BEOPEN PYTHON OPEN SOURCE LICENSE AGREEMENT VERSION 1

1. This LICENSE AGREEMENT is between BeOpen.com ("BeOpen"), having an
office at 160 Saratoga Avenue, Santa Clara, CA 95051, and the
Individual or Organization ("Licensee") accessing and otherwise using
this software in source or binary form and its associated
documentation ("the Software").

2. Subject to the terms and conditions of this BeOpen Python License
Agreement, BeOpen hereby grants Licensee a non-exclusive,
royalty-free, world-wide license to reproduce, analyze, test, perform
and/or display publicly, prepare derivative works, distribute, and
otherwise use the Software alone or in any derivative version,
provided, however, that the BeOpen Python License is retained in the
Software, alone or in any derivative version prepared by Licensee.

3. BeOpen is making the Software available to Licensee on an "AS IS"
basis.  BEOPEN MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, BEOPEN MAKES NO AND
DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF THE SOFTWARE WILL NOT
INFRINGE ANY THIRD PARTY RIGHTS.

4. BEOPEN SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF THE
SOFTWARE FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS
AS A RESULT OF USING, MODIFYING OR DISTRIBUTING THE SOFTWARE, OR ANY
DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.

5. This License Agreement will automatically terminate upon a material
breach of its terms and conditions.

6. This License Agreement shall be governed by and interpreted in all
respects by the law of the State of California, excluding conflict of
law provisions.  Nothing in this License Agreement shall be deemed to
create any relationship of agency, partnership, or joint venture
between BeOpen and Licensee.  This License Agreement does not grant
permission to use BeOpen trademarks or trade names in a trademark
sense to endorse or promote products or services of Licensee, or any
third party.  As an exception, the "BeOpen Python" logos available at
http://www.pythonlabs.com/logos.html may be used according to the
permissions granted on that web page.

7. By copying, installing or otherwise using the software, Licensee
agrees to be bound by the terms and conditions of this License
Agreement.


CNRI LICENSE AGREEMENT FOR PYTHON 1.6.1
---------------------------------------

1. This LICENSE AGREEMENT is between the Corporation for National
Research Initiatives, having an office at 1895 Preston White Drive,
Reston, VA 20191 ("CNRI"), and the Individual or Organization
("Licensee") accessing and otherwise using Python 1.6.1 software in
source or binary form and its associated documentation.

2. Subject to the terms and conditions of this License Agreement, CNRI
hereby grants Licensee a nonexclusive, royalty-free, world-wide
license to reproduce, analyze, test, perform and/or display publicly,
prepare derivative works, distribute, and otherwise use Python 1.6.1
alone or in any derivative version, provided, however, that CNRI's
License Agreement and CNRI's notice of copyright, i.e., "Copyright (c)
1995-2001 Corporation for National Research Initiatives; All Rights
Reserved" are retained in Python 1.6.1 alone or in any derivative
version prepared by Licensee.  Alternately, in lieu of CNRI's License
Agreement, Licensee may substitute the following text (omitting the
quotes): "Python 1.6.1 is made available subject to the terms and
conditions in CNRI's License Agreement.  This Agreement together with
Python 1.6.1 may be located on the internet using the following
unique, persistent identifier (known as a handle): 1895.22/1013.  This
Agreement may also be obtained from a proxy server on the internet
using the following URL: http://hdl.handle.net/1895.22/1013".

3. In the event Licensee prepares a derivative work that is based on
or incorporates Python 1.6.1 or any part thereof, and wants to make
the derivative work available to others as provided herein, then
Licensee hereby agrees to include in any such work a brief summary of
the changes made to Python 1.6.1.

4. CNRI is making Python 1.6.1 available to Licensee on an "AS IS"
basis.  CNRI MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, CNRI MAKES NO AND
DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON 1.6.1 WILL NOT
INFRINGE ANY THIRD PARTY RIGHTS.

5. CNRI SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
1.6.1 FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON 1.6.1,
OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.

6. This License Agreement will automatically terminate upon a material
breach of its terms and conditions.

7. This License Agreement shall be governed by the federal
intellectual property law of the United States, including without
limitation the federal copyright law, and, to the extent such
U.S. federal law does not apply, by the law of the Commonwealth of
Virginia, excluding Virginia's conflict of law provisions.
Notwithstanding the foregoing, with regard to derivative works based
on Python 1.6.1 that incorporate non-separable material that was
previously distributed under the GNU General Public License (GPL), the
law of the Commonwealth of Virginia shall govern this License
Agreement only as to issues arising under or with respect to
Paragraphs 4, 5, and 7 of this License Agreement.  Nothing in this
License Agreement shall be deemed to create any relationship of
agency, partnership, or joint venture between CNRI and Licensee.  This
License Agreement does not grant permission to use CNRI trademarks or
trade name in a trademark sense to endorse or promote products or
services of Licensee, or any third party.

8. By clicking on the "ACCEPT" button where indicated, or by copying,
installing or otherwise using Python 1.6.1, Licensee agrees to be
bound by the terms and conditions of this License Agreement.

        ACCEPT


CWI LICENSE AGREEMENT FOR PYTHON 0.9.0 THROUGH 1.2
--------------------------------------------------

Copyright (c) 1991 - 1995, Stichting Mathematisch Centrum Amsterdam,
The Netherlands.  All rights reserved.

Permission to use, copy, modify, and distribute this software and its
documentation for any purpose and without fee is hereby granted,
provided that the above copyright notice appear in all copies and that
both that copyright notice and this permission notice appear in
supporting documentation, and that the name of Stichting Mathematisch
Centrum or CWI not be used in advertising or publicity pertaining to
distribution of the software without specific, written prior
permission.

STICHTING MATHEMATISCH CENTRUM DISCLAIMS ALL WARRANTIES WITH REGARD TO
THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS, IN NO EVENT SHALL STICHTING MATHEMATISCH CENTRUM BE LIABLE
FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

ZERO-CLAUSE BSD LICENSE FOR CODE IN THE PYTHON DOCUMENTATION
----------------------------------------------------------------------

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
~~~~

<a id="l3"></a>
### L3: MIT

Applies to: preact 10.29.8.

~~~~text
The MIT License (MIT)

Copyright (c) 2015-present Jason Miller

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
~~~~

<a id="l4"></a>
### L4: MIT

Applies to: @preact/signals 2.11.2; @preact/signals-core 1.14.4.

~~~~text
The MIT License (MIT)

Copyright (c) 2022-present Preact Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
~~~~

<a id="l5"></a>
### L5: MIT

Applies to: @tiptap/core 3.31.3; @tiptap/extension-blockquote 3.31.3; @tiptap/extension-bold 3.31.3; @tiptap/extension-code 3.31.3; @tiptap/extension-code-block 3.31.3; @tiptap/extension-document 3.31.3; @tiptap/extension-hard-break 3.31.3; @tiptap/extension-heading 3.31.3; @tiptap/extension-horizontal-rule 3.31.3; @tiptap/extension-image 3.31.3; @tiptap/extension-italic 3.31.3; @tiptap/extension-link 3.31.3; @tiptap/extension-list 3.31.3; @tiptap/extension-paragraph 3.31.3; @tiptap/extension-strike 3.31.3; @tiptap/extension-table 3.31.3; @tiptap/extension-text 3.31.3; @tiptap/extension-underline 3.31.3; @tiptap/extensions 3.31.3; @tiptap/markdown 3.31.3; @tiptap/pm 3.31.3; @tiptap/starter-kit 3.31.3.

~~~~text
MIT License

Copyright (c) 2025, Tiptap GmbH

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
~~~~

<a id="l6"></a>
### L6: MIT

Applies to: @tiptap/pm (third-party list) 3.31.3.

~~~~text
# Third-party licenses

This package re-exports packages from the [ProseMirror](https://prosemirror.net) project.

ProseMirror is licensed under the MIT License.

Copyright (C) Marijn Haverbeke <marijn@haverbeke.berlin> and others

The following ProseMirror packages are re-exported by this package:

- prosemirror-changeset
- prosemirror-commands
- prosemirror-dropcursor
- prosemirror-gapcursor
- prosemirror-history
- prosemirror-inputrules
- prosemirror-keymap
- prosemirror-model
- prosemirror-schema-list
- prosemirror-state
- prosemirror-tables
- prosemirror-transform
- prosemirror-view

---

## [MIT License (ProseMirror)](https://code.haverbeke.berlin/prosemirror/prosemirror/src/branch/main/LICENSE)

Copyright (C) 2015-2017 by Marijn Haverbeke <marijn@haverbeke.berlin> and others

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
~~~~

<a id="l7"></a>
### L7: MIT

Applies to: linkifyjs 4.3.3.

~~~~text
Copyright (c) 2024 Nick Frasser

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
~~~~

<a id="l8"></a>
### L8: MIT

Applies to: marked 17.0.6.

~~~~text
# License information

## Contribution License Agreement

If you contribute code to this project, you are implicitly allowing your code
to be distributed under the MIT license. You are also implicitly verifying that
all code is your original work. `</legalese>`

## Marked

Copyright (c) 2018+, MarkedJS (https://github.com/markedjs/)
Copyright (c) 2011-2018, Christopher Jeffrey (https://github.com/chjj/)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

## Markdown

Copyright © 2004, John Gruber
http://daringfireball.net/
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
* Neither the name “Markdown” nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

This software is provided by the copyright holders and contributors “as is” and any express or implied warranties, including, but not limited to, the implied warranties of merchantability and fitness for a particular purpose are disclaimed. In no event shall the copyright owner or contributors be liable for any direct, indirect, incidental, special, exemplary, or consequential damages (including, but not limited to, procurement of substitute goods or services; loss of use, data, or profits; or business interruption) however caused and on any theory of liability, whether in contract, strict liability, or tort (including negligence or otherwise) arising in any way out of the use of this software, even if advised of the possibility of such damage.
~~~~

<a id="l9"></a>
### L9: MIT

Applies to: orderedmap 2.1.1; w3c-keyname 2.2.8.

~~~~text
Copyright (C) 2016 by Marijn Haverbeke <marijn@haverbeke.berlin> and others

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
~~~~

<a id="l10"></a>
### L10: MIT

Applies to: prosemirror-commands 1.7.2; prosemirror-dropcursor 1.8.4; prosemirror-gapcursor 1.4.1; prosemirror-history 1.5.0; prosemirror-keymap 1.2.3; prosemirror-model 1.25.12; prosemirror-schema-list 1.5.1; prosemirror-state 1.4.4; prosemirror-transform 1.12.2; prosemirror-view 1.42.6.

~~~~text
Copyright (C) 2015-2017 by Marijn Haverbeke <marijn@haverbeke.berlin> and others

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
~~~~

<a id="l11"></a>
### L11: MIT

Applies to: prosemirror-tables 1.8.5.

~~~~text
Copyright (C) 2015-2016 by Marijn Haverbeke <marijnh@gmail.com> and others

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
~~~~

<a id="l12"></a>
### L12: MIT

Applies to: rope-sequence 1.3.4.

~~~~text
Copyright (C) 2016 by Marijn Haverbeke <marijn@haverbeke.berlin>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
~~~~

<a id="l13"></a>
### L13: SIL Open Font License 1.1

Applies to: Inter.

~~~~text
Copyright 2020 The Inter Project Authors (https://github.com/rsms/inter)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
https://openfontlicense.org


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.
~~~~

<a id="l14"></a>
### L14: SIL Open Font License 1.1

Applies to: Montserrat.

~~~~text
Copyright 2024 The Montserrat.Git Project Authors (https://github.com/JulietaUla/Montserrat.git)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
https://openfontlicense.org


-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded, 
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.
~~~~

<a id="l15"></a>
### L15: MIT

Applies to: Feather (the Settings gear shape).

~~~~text
The MIT License (MIT)

Copyright (c) 2013-2023 Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
~~~~

<a id="l16"></a>
### L16: ISC, with Feather's MIT notice

Applies to: Lucide (credited; carries Feather's MIT notice).

~~~~text
ISC License

Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

---

The following Lucide icons are derived from the Feather project:

airplay, alert-circle, alert-octagon, alert-triangle, aperture, arrow-down-circle, arrow-down-left, arrow-down-right, arrow-down, arrow-left-circle, arrow-left, arrow-right-circle, arrow-right, arrow-up-circle, arrow-up-left, arrow-up-right, arrow-up, at-sign, calendar, cast, check, chevron-down, chevron-left, chevron-right, chevron-up, chevrons-down, chevrons-left, chevrons-right, chevrons-up, circle, clipboard, clock, code, columns, command, compass, corner-down-left, corner-down-right, corner-left-down, corner-left-up, corner-right-down, corner-right-up, corner-up-left, corner-up-right, crosshair, database, divide-circle, divide-square, dollar-sign, download, external-link, feather, frown, hash, headphones, help-circle, info, italic, key, layout, life-buoy, link-2, link, loader, lock, log-in, log-out, maximize, meh, minimize, minimize-2, minus-circle, minus-square, minus, monitor, moon, more-horizontal, more-vertical, move, music, navigation-2, navigation, octagon, pause-circle, percent, plus-circle, plus-square, plus, power, radio, rss, search, server, share, shopping-bag, sidebar, smartphone, smile, square, table-2, tablet, target, terminal, trash-2, trash, triangle, tv, type, upload, x-circle, x-octagon, x-square, x, zoom-in, zoom-out

The MIT License (MIT) (for the icons listed above)

Copyright (c) 2013-present Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
~~~~

## Differences found when the licence files were checked

- **Inter** (`vendor/fonts/inter/OFL.txt`): identical to the Google Fonts file (`ofl/inter/OFL.txt`) except one line in the introduction, which gives the address `https://openfontlicense.org` where the Google Fonts file gives `https://scripts.sil.org/OFL`. The licence terms are the same.
- **Montserrat** (`vendor/fonts/montserrat/OFL.txt`): identical to the Google Fonts file (`ofl/montserrat/OFL.txt`) except that ours ends with a final newline.
- **et_xmlfile**: `vendor/licenses/` holds its `LICENCE.python` but not its own `LICENCE.rst` (the MIT text). The MIT text is given in L1 above; the file itself is not yet in the tree.
