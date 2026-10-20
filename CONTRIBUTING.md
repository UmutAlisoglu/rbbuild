<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# Making contributions

## Thank You!

Before we get to the _fine print_ and nitty gritty of contributing, let us
start by saying **Thank you!** for considering to make a contribution to this
Open Source project. Open Source exists and thrives because of people like
you, who are willing to make contributions, share their knowledge with fellow
developers.


## Legal

### License

Your contributions must be licensed under MIT License.


### Contribution License Agreement

By contributing to this project, you are agreeing to the
[Developer Certificate of Origin 1.1](https://developercertificate.org/):

```text
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```


## Community guidelines

rbbuild is a community project. We strive to work in accordance with these
values:

- _Openness_: We welcome *all developers* to make contributions,
  regardless of gender, age, sexual orientation, education, experience,
  affiliation with group, business unit, division or other discriminating
  factors.
- _Transparency_: We make our code, documentation and communication available
  for everybody.
- _Voluntariness_: We prefer contributions to be made voluntarily by
  intrinsically motivated community members.
- _Self-determination_: As a community, we ourselves decide **what** to work on,
  **when** to do it, with **which tools** we work and **what processes** we apply.
- _Meritocracy_: Rank in our community is to be granted based on meritocratic
  principles. That is: rank is determined by the amount and quality of
  contributions made to the community - both technically and socially.

In our daily work, this means that

- we treat each other with utmost respect,
- we consider voluntary contributions as gifts and treat both our contributions
  and our contributors accordingly,
- we happily invest time into sharing our knowledge with fellow community
  members, even if it slows down progress in the short term and
- we value communication "out in the open" (our forum, our issue tracker,
  in Pull Requests) to one-on-one communication.


## Contact

The main way to contact us is via our [issue tracker](https://github.com/boschglobal/rbbuild/issues).

If, for some reason, you prefer kicking off the collaboration in a personal
conversation, please contact the maintainers of this repository, which are
listed in this repository's `README.md`.


### How to submit a bug report?

Found a bug? Great! A core task in improving our software is to identify any
flaws that may be present. The best place to report a bug is to [create an issue in
our issue tracker](https://github.com/boschglobal/rbbuild/issues).


### How to submit a feature request?

If you have suggestions for us on how to improve our code or
our documentation or have a new feature in mind, please by all
means do let us know. The same rules apply as for bug reports:
either add a new issue outlining your suggestion in our
[issue tracker](https://github.com/boschglobal/rbbuild/issues).


## How to contribute?

If you have fixed a bug or have developed that new feature
you would like to make available to your fellow users, or even
if you have fixed whitespace or formatting issues, we'd like
to encourage you to contribute that to our codebase. In this repository,
we use _Pull Requests_ to facilitate all contributions. Every
Pull Request will be peer reviewed by at least one community
member, which is a great way to get in touch with each other.


### Coding Conventions

We have coding style guides in place for all our projects.

There are few rules to obey when contributing:
* For Python code, we follow [PEP-8](https://peps.python.org/pep-0008) as much
  as possible.
* If you are modifying existing code files, do not include style changes of
  the existing code.
  Exception: the purpose of your pull request is a style guide related.
* Be mindful about stray whitespaces, dead code, and commented-out code: those
  should not be part of your PR.
* Unless there is a very good reason, never add third-party material to our
  repositories. Instead, add a dependency via pyproject.toml.
* Only source code and other text files should be added to the repository.
  The addition of binary files should be avoided.
* Make sure that third-party component licenses are compliant with our own
  license.
  Non-OSS licenses (propietary/commercial) should be generally avoided.
* Finally, test your code before submitting! Use [pytest](https://pytest.org/) to run
  unit/integration tests, and [Ruff](https://docs.astral.sh/ruff/) (via
  `rbbuild --sca`, which applies the quality configuration) as static code analyzer.
* If you use an AI coding assistant, the rules in [AGENTS.md](AGENTS.md) apply
  as well.


#### Clean Code

More important than writing code that adheres to our style guide is writing
_Clean Code_. We consider code to be _clean_, if it

- works,
- is easy to understand,
- is easy to modify and
- is easy to test.

Any code contribution will be reviewed by us with respect to these criteria.
We are more than happy and indeed consider it a core part of _being Open Source_
to invest time mentoring junior developers to help them create _cleaner_ code
and to improve future contributions.

In addition to these principles of clean code, we also try to _design our
architectures for participation_. That, to us, means to avoid unnecessary
complexity, tight coupling or complex dependency relationships.


### Testing conventions

We are convinced that writing testable code and writing tests is a precondition
for any software to be maintainable. Even though we do not prescribe fixed
coverage thresholds for our tests, we encourage (and often will require) you to
write tests for code that needs to be maintainable where the effort is not
excessive. This means that we

- aim to write code with testability in mind (following the test-first principle)
- write tests for everything we can test
- expose a submitted bug with a test first, before we implement a fix.

We also aim to write our tests such that they can be read as a specification
(because we usually don't spend time writing those). In practice, this means
that we use long, verbose and expressive names for tests which convey the
condition being tested.

In our experience, writing tests can actually be a lot of fun. As a programmer,
you have more leeway to experiment and try new programming approaches when
writing tests. That is why we often try out new language features in our test
code, first. And if you're following the test-first principle, it's always
quite rewarding to see those red test cases continue to turn green, once the
implementation is complete. Finally, only adequate tests will empower you to
continuously improve your codebase with refactorings, as they provide the
reassurance that you didn't break anything accidentally.


### Commit Message Conventions

Commit messages on `feature` branches should briefly describe the change
introduced with the commit. Ticket IDs as part of the commit message are
recommended but not mandatory.
Here are some examples of good commit messages:

    "Added method to access number of received bytes to BusConnection (#4711)"
    "#0815: Fixed typo in README.md"

Following this convention automatically associates the commit, and thus the
branch and Pull Request that it belongs to with the given issue in our issue
tracker and vice versa.

Pull requests are generally squashed before merging. Merge requests MUST
contain the ticket ID to link the PR with a specific ticket.


### Writing documentation

We follow these principles when documenting code:

- We aim at keeping documentation as close to the asset being documented as
  possible. That is, where sensible, we use inline code documentation.
- We use [PlantUML](http://plantuml.com) for specifying UML diagrams in the
  code in order to be tool agnostic and allow everybody to adapt and improve it.
- We favor [Markdown](https://daringfireball.net/projects/markdown) or other
  text-based means of generating documentation and try not to use proprietary
  tools, such as Word or PowerPoint for that.
- We aim at providing our users with easy to understand instructions on how to
  use our code in each repository's `README.md`.
- We favor code examples over analytical descriptions of our codebase.
- We keep our documentation as comprehensive and terse as possible. That said,
  we use AI-generated documentation that is curated and checked thoroughly.
  Text that is merely replicating and describing all steps of the source code
  is usually not required.


### Pull Requests

Pull Requests are our main vehicle for submitting, reviewing and merging new
code into our codebase. A Pull Request is more than just an easy interface to
git: it is a powerful collaboration and communication tool. They are especially
well suited to share knowledge and onboard new contributors. So if you are new
to the community, submitting Pull Requests is an excellent way for you to engage
with us and for us to help you get started. Discussions and the Q&A that often
accompanies Pull Requests are archived and linkable and we thus use them to
disseminate knowledge about our codebase.


#### Conventions for communicating in Pull Requests

[This article](https://hugooodias.medium.com/the-anatomy-of-a-perfect-pull-request-567382bb6067)
nicely summarizes how to (and how not to) communicate in Pull Requests. Apart
from the social aspects of interactions, we follow a couple of conventions for
signaling.

Here are common signals:

- **Add s.o. as reviewer**: _"I'd like you to review my PR and I will not merge
  w/o your approval!"_
- **Approve a PR**: _"I'm ok with merging this PR. If there are open tasks, I
  expect these to be finished before merging and I trust you to do this w/o
  another review!"_
- **Request Changes**: _"I am not ok with merging this PR and I require changes to
  be made. I will re-review this PR after changes are made!"_
- **@-mention s.o. in PR description with /CC prefix**: _"I'd like you to have a
  look at this PR but I'm not asking for your formal approval!"_
- **@-mention s.o. in PR description with /FYI prefix**: _"Just so you know,
  we're working on this!"_
- **@-mention s.o. in comment as part of question**: _"Can you please reply to
  my question with a comment?"_
- **Reviewer adds task to PR**: _"This needs to be fixed before I merge this
  PR!"_
- **Author of PR adds task in response to comment of reviewer**: _"I will finish
  this task before merging!"_
- **Mark task as completed**: _"This task is finished and I have pushed the
  changes!"_
- **Add like**: _"I agree with the statements made in the liked comment!"_
- **Add link to new issue**: _"I will not make the change in this PR but will
  take care of it later!"_

Generally speaking, when signaling, try to

- be respectful,
- be concise,
- be specific,
- clearly state your expectation and
- use links where possible (to files, lines in files, commits, pull requests,
  people, issues, other comments, ...)


#### Definition of done

We use the following checklist to determine if a PR is ready to merge:

- If CI/CD is in place, the last build is _green_
- If new code was added or if a bug was fixed, corresponding tests have been added
- All tasks added by reviewers are resolved
- At least one maintainer has approved the PR and none has signaled _Needs Work_


#### General tips

- Keep your PRs as small as possible. The smaller the PR the higher the
  velocity of review and acceptance.
- Avoid conflating multiple issues in one PR. Aside from usually leading
  to huge PRs and making the job of a reviewer unnecessarily harder.
- Write a good description to allow the reviewer to quickly get an overview of
  your changes.
- Don't add more than two reviewers if you expect all of them to review. This
  will most likely block you.


## Other contributions

You don't have to be a coder to make a valuable contribution to this community!
There are many contributions that you can make as a non-coder that will be very
valuable to the community, such as

- giving feedback of any kind,
- reporting bugs,
- requesting features,
- adding new or improving existing documentation,
- helping other users to use our software,
- asking and/or answering questions in our forums,
- promoting our community and our software within your company or
- designing artwork for our software or internet presence.

