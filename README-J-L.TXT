%-----------------------------------------------------------------------------
% Beginning of README-J-L.TXT
%-----------------------------------------------------------------------------

                    AMERICAN MATHEMATICAL SOCIETY
                          201 Charles Street
                   Providence, RI  02904-2294  USA


AMS JOURNAL STYLE PACKAGE
-------------------------

This package contains files to help authors use AMS-LaTeX to prepare a
journal article for publication at the AMS.  We assume that the following
software is installed on your system.

    LaTeX           version 2e, December 1995 or later
    AMS classes     version 2.20.1, July 2009 or later
    amsmath         version 2.13, July 2000 or later
    AMSFonts        version 2.0, January 1995 or later

The current versions of these collections are included in the "required"
subset of TeX Live, as well as in most other common distributions.

If you have an older version of LaTeX or AMS-LaTeX, please upgrade,  You
can retrieve the current versions of amsmath and the AMS classes from
CTAN at

    http://www.ctan.org/tex-archive/macros/latex/required

We also assume that you are familiar with LaTeX and AMS-LaTeX document
structuring commands such as \section, \footnote, \newtheorem, etc., and
with the techniques for inputting math expressions.

1) This package contains the following files.

general files

    README-J-L.TXT         overview of journal package (this file)
    Author_Handbook_Journals.pdf   AMS Author Handbook
    creating-graphics.pdf  Creating graphics for use in books and journals
    amsart.cls             basis for all journal-specific document classes

journal-specific files

    *-l.cls         document class file
    *-template.tex  template file

sample article file

    journal.tex     journal sample article

(where "*" represents the specific journal code)

2) Start your article by making a copy of the template to <uniquename>.tex,
using a distinct name (perhaps your last name) in place of <uniquename>.
Fill in the top matter (title, author(s), etc.) following the instructions
that appear as comments in the file.  Input the text of the article
between \begin{document} and \end{document}.

3) More detailed instructions are given in the Author Handbook.  This
manual is also available via the web from a link on the page
     http://www.ams.org/arc/handbook
The handbook includes a checklist to be consulted, before keyboarding
your manuscript, in order to avoid the most common problems, as well as
detailed instructions for submitting your files to the AMS.

4) If your article will contain graphics, print out, or view on screen,
the file creating-graphics.pdf and read it.  This file contains general
and specific guidelines for preparation of graphics (line art,
photographs, and other forms of illustrations) in a manner that will
ensure their accurate reproduction in print and on-line.

5) By default, the "sample article file" listed above uses the basic AMS
journal article style, amsart.cls.

Replace the \documentclass{amsart} line in the sample article file by
\documentclass{*-l}, where * is the specific journal code, and then LaTeX
the file, in order to view the printed style for the intended journal.

Do NOT use the sample article as a "starter" for your article.  Use
the template file instead.  The sample article should be used only for
your reference.

amsart.cls is included in this package because of the 2010 update to the
Mathematics Subject Classification.  This is the only significant change
to amsart from the version in TeX Live distributions since 2005; the
updated version of amsart.cls has been included in TeX Live since 2009,
so if you are using that distribution, you should delete the copy
included in this package.


Should you have any technical questions that aren't answered by the FAQ,
please contact our Technical Support Group.  The most effective method
is to send electronic mail to tech-support@ams.org, including a concise
statement of the problem, along with (if appropriate) a brief file that
illustrates the problem and the log of your attempt to LaTeX the file.
If email is not an option, you can call 800-321-4AMS (800-321-4267,
in the U.S. or Canada) or 401-455-4080, or write to Technical Support,
Publications Technical Group, AMS, 201 Charles Street, Providence,
RI 02904-2294.

[2019/11/12, readme-j-l.txt]
%-----------------------------------------------------------------------------
% End of README-J-L.TXT
%-----------------------------------------------------------------------------
