% \def\filename{mcom-l.cls}
% \def\fileversion{2.02}
% \def\filedate{2016/10/18}
%
% \iffalse meta-comment
%
% American Mathematical Society
% Technical Support
% Publications Technical Group
% 201 Charles Street
% Providence, RI 02904
% USA
% tel: (401) 455-4080
%      (800) 321-4267 (USA and Canada only)
% fax: (401) 331-3842
% email: tech-support@ams.org
%
% Copyright 2007, 2016 American Mathematical Society.
%
% This work may be distributed and/or modified under the
% conditions of the LaTeX Project Public License, either version 1.3c
% of this license or (at your option) any later version.
% The latest version of this license is in
%   http://www.latex-project.org/lppl.txt
% and version 1.3c or later is part of all distributions of LaTeX
% version 2005/12/01 or later.
% 
% This work has the LPPL maintenance status `maintained'.
% 
% The Current Maintainer of this work is the American Mathematical
% Society.
% 
% \fi

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{mcom-l}
              [2016/10/18 v2.02 MCOM Author Class]

\DeclareOption*{\PassOptionsToClass{\CurrentOption}{amsart}}
\ProcessOptions\relax

\LoadClass{amsart}[2009/07/02]

\def\publname{MATHEMATICS OF COMPUTATION}

\def\ISSN{0025-5718}

\copyrightinfo{\currentyear}%    % copyright year
  {American Mathematical Society}% copyright holder

\renewcommand{\datename}{Received by the editor}

\endinput
