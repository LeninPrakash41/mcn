# MCN Developer Club

The MCN Developer Club is for students and professionals who build apps in MCN. Anyone with an account can join, build an app in Studio, and launch it for review. Approved apps are listed in the club's marketplace, where the best win awards and promising ones are picked out for funding, recognition or showcasing. Every developer who launches an app gets a certificate.

The club runs on your MCN account server (hosted Studio, `mcn studio --hosted`). Installed Studio uses it after you **Sign In**.

## Joining

Open Studio's **Club** tab and join with your name, whether you're a **student** (with your college or university) or a **professional** (with your company), and optionally your course and year or job title.

## Launching an app for review

In the **Club** tab, choose **Launch for review**, give the app a title, a one-line description, a category and a short explanation, and send it. Studio sends `backend/main.mcn` and `ui/app.mcn` from your workspace. The app must parse; reviewers also see its type check and [app map](#/guide/ai-agents) (screens, endpoints, tables, tests, whether it uses AI, and any problems found). Submitted code is checked, never run, on the server.

A project is **In review** until a reviewer decides:

| Decision | What happens |
|---|---|
| Approved | It's listed in the marketplace, and you get a **Certified MCN Developer** certificate for it |
| Changes requested | You see the reviewer's notes; fix the app and **send this workspace as a new version** |
| Not approved | You see why; you can send a new version later |

You can withdraw a project at any time.

## The marketplace

`/club` on the account server lists approved apps for anyone, signed in or not. Filter by award, by spotlight, by students or professionals, or search by app, person, college or company. Each app has its own page with its description, awards and the reviewers' notes, its code, and **Open in Studio**, which copies it into your workspace to try or build on.

### Awards

Reviewers recognise approved apps in five categories:

- **Best Overall Application**
- **Best Innovation**
- **Best Technical Implementation**
- **Best Use of MCN**
- **Best AI-Powered Application**

An app can win several. Each award comes with a certificate.

### Spotlights

A reviewer can mark a promising app as a **funding candidate**, for **recognition**, or for the **showcase**. The marketplace can be filtered by each.

## Certificates

| Certificate | Given |
|---|---|
| Certificate of Participation | to every member, when they first launch an app for review |
| Certified MCN Developer | for each approved app |
| Award | for each award an app wins |

Each certificate has a code (like `MCN-7KX2Q9PDRT`) and its own page, `/club/certificate/<code>`, which anyone can open to check it's genuine, and print or save as a PDF. **My work** in the Club tab lists yours.

## Reviewing

Admins and anyone given the `reviewer` role (Admin → Users) see a **Review** tab in the Club panel:

- **The dashboard**: members (students and professionals), projects by status, certificates issued, approved apps that use AI, awards and spotlights given, and the colleges and companies with the most approved apps. This is where you track the ideas coming through the club.
- **The queue**: each project with its checks and code. Approve it, or request changes or reject it with notes for the developer (notes are required for those).
- **The marketplace**: give or take back awards, and set a spotlight.
