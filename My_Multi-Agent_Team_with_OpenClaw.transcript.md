# SPEAKER_01 - 00:00:00
Well, sitting on my desk is a new Mac mini that I set up just for the purpose of running my team of AI agents using Open Claw.

# SPEAKER_01 - 00:00:03
I've got a developer, a marketer, a project manager, and a system admin. They each have their own personality. They've got a queue of tasks tracked in this custom dashboard that I built. And I'm chatting with them in Slack, just like I would with my real team members, except they're agents powered by Open Claw and various large language models. What a time this is.

# SPEAKER_01 - 00:00:12
But getting this up and running was not a plug-and-play situation. Over the past week and many late nights, I had to figure out my answers to question after question, some technical, some strategic.

# SPEAKER_01 - 00:00:17
Should I order a new Mac mini, or can I run Open Claw on a VPS? What's this going to cost me in API tokens? Can I use my Claude Max plan? What chat tool is best for my agents—Telegram, WhatsApp, or Slack?

# SPEAKER_01 - 00:00:23
Should I have a power-of-one agent? Or can I set up a team of agents? And am I going to need a custom dashboard for managing them?

# SPEAKER_01 - 00:00:27
And let's not forget about security. What should my agents be able to access? How should I think about safeguards? And most importantly, what's my use case here? What will I have my team of agents actually do for me?

# SPEAKER_01 - 00:00:33
Today I'll share where I've landed on all of those questions, and I'll show you my setup for all of it.

# SPEAKER_01 - 00:00:36
I didn't see the appeal of Open Claw at first. Back when it was called Clawbot and then Moltbot, and it was buzzing around Twitter a couple of weeks ago, everyone was talking about having their agent respond to their emails for them, or book flights, or order takeout.

# SPEAKER_01 - 00:00:46
I don't want or need an AI agent in my personal life, and I don't even want it to manage my calendar. But then I started thinking about a real challenge that I've been having in my business and how setting up Open Claw could help me solve it.

# SPEAKER_01 - 00:00:51
I run this YouTube channel, build on my Builder Methods Pro courses, and a weekly newsletter. And thanks to things like Claude Code, building things has never been easier, but building is only half of what I do.

# SPEAKER_01 - 00:00:57
I develop training content, I manage a publishing pipeline, and I oversee my membership business. But lately, I've been bottlenecked.

# SPEAKER_01 - 01:00:00
There's so much more that I want to create and deliver if only I had the bandwidth. In my past businesses, I solved this by hiring real teams and building processes to help us scale, and that worked, but the overhead was real too.

# SPEAKER_01 - 01:00:04
When I gave Open Claw another look, I asked a different question: not "do I want a personal assistant?" but "what if this could fill roles on my team?"

# SPEAKER_01 - 01:00:08
And now I'm convinced that this paradigm—autonomous agents with defined roles running on their own machines—is here to stay.

# SPEAKER_01 - 01:00:13
Now, Open Claw is just the first generation of what I think will be much bigger. So I want to be figuring this out now, and maybe this video can help you get started too.

# SPEAKER_01 - 01:00:18
If you're new here, I'm Brian Castle. I help builders stay ahead of the curve with AI. Every Friday, I send my Builder Briefing. That's a free, five-minute read where I give you my no-hype take on making this transition to adopting AI.

# SPEAKER_01 - 01:00:26
You can get yours by going to buildermethods.com. And if you're serious about leveling up, check out Builder Methods Pro, where you can join our community and get training for builders.

# SPEAKER_01 - 01:00:32
So what actually is Open Claw? It used to be called Claude Bot and then Molt Bot. And how is this actually different from how you might use Claude Code or any other agent?

# SPEAKER_01 - 01:00:38
The core of Open Claw is what's called the gateway. That's a process running on a machine, which shouldn't be your personal machine, but we'll talk about security in a moment.

# SPEAKER_01 - 01:00:44
The Open Claw gateway can run tools. It could use a browser. It could execute bash scripts. Of course, Claude Code can do a lot of that too. But what makes Open Claw different is that it's always on. It maintains a persistent workspace with memory and session logs.

# SPEAKER_01 - 01:00:54
You can chat with your agents through Telegram or Slack and delegate tasks that they can do on their own in the background.

# SPEAKER_01 - 01:00:59
So that's a fundamentally different paradigm from you personally managing Claude Code sessions in your terminal.

# SPEAKER_01 - 01:01:02
Open Claw is closer to having teammates who do their work on their own workstations.

# SPEAKER_01 - 01:01:04
The first question is where should this thing run? Now, I don't recommend you run Open Claw on your daily-driver machine. You don't want to give it unfettered access to your files and your accounts. Even if you isolate it with something like Docker, your machine would need to be on and awake 24/7 for your agents to work.

# SPEAKER_01 - 01:01:13
So Open Claw needs its own dedicated machine. That could be a cloud VPS starting at around five bucks a month, or it could be a physical machine. It doesn't have to be a Mac mini, any kind of computer on your network.

# SPEAKER_01 - 01:01:21
Both are valid and a lot of people are doing well with the VPS setups. But I went ahead and I spent the 600 bucks on a new Mac mini M4. Call me old school, but I like to be able to screen share into it, see the desktop, install things, and manage it visually.

# SPEAKER_01 - 01:01:31
And I SSH in too when I just need to run a quick command. And if I end up using my agent team for all the use cases that I have in mind, I'll need more storage and bandwidth than the cheap VPS tiers offer.

# SPEAKER_01 - 01:01:39
So the cost would start to balance out anyway. And hey, if none of this works out, I'll throw that Mac mini up in my home music studio. I'll use it up there.

# SPEAKER_01 - 01:01:45
So I've got the dedicated machine, but that's just the first layer. I need to think carefully about what my agents can and can't access.

# SPEAKER_01 - 01:01:50
Now, this is where the hiring metaphor really kicked in. If I'm bringing someone onto my team, I wouldn't give them access to my personal laptop or let them loose on a browser where I'm logged into everything.

# SPEAKER_01 - 01:01:59
Now, an employee would get their own machine, their own email, and access to the files and services that they need with the right permissions. Nothing more.

# SPEAKER_01 - 02:00:06
So that's what I did. I set up a dedicated email address for my agents. I created a GitHub username that I can invite to specific repos. I can grant and revoke access to services just like I would with any other team member.

# SPEAKER_01 - 02:00:15
Now, files were a bit trickier. I want easy two-way syncing between my computer and the Open Claw workspace on the Mac mini, especially since I'm developing a brain system where all my business activity gets logged into markdown files that my agents can access and work with.

# SPEAKER_01 - 02:00:27
More on the brain, maybe another time. So all my files live either in GitHub repos or my main Dropbox account.

# SPEAKER_01 - 02:00:32
But I don't want to just share my personal Dropbox with Open Claw. That gives it access to way too much.

# SPEAKER_01 - 02:00:36
So I had Open Claw set up its own Dropbox account. And so the specific folders that I want to share between my main Mac and the Open Claw Mac mini, both Dropbox accounts have access to those. And so everything else stays walled off.

# SPEAKER_01 - 02:00:46
All right, let's talk about costs, because if you're not careful, you can easily run up hundreds or even thousands of dollars in token costs just chatting with your agents and running tasks.

# SPEAKER_01 - 02:00:55
I blew past $200 in the first two days of setting up my system. Now, I already pay for a Claude Max plan and I was hoping that I could just use that.

# SPEAKER_01 - 03:00:01
But then I heard the stories of accounts being shut down because this type of usage might be against Anthropic's terms of service.

# SPEAKER_02 - 03:00:06
And then within a few days, I upgraded to the $200 subscription, or euros because it's in Austria.

# SPEAKER_02 - 03:00:10
And he was in love with that thing. That for me was like a very early product validation. It's like, I built something that captures people.

# SPEAKER_02 - 03:00:15
And then a few days later, Anthropic blocked him because based on their rules, using the subscription is problematic or whatever.

# SPEAKER_01 - 03:00:21
So there's real ambiguity there. And I genuinely wish that there would be some official word one way or the other.

# SPEAKER_01 - 03:00:26
Now, I intend to play by the rules. So here's where I landed. My Claude Max plan is for my personal use with Claude and Claude Code on my devices when I'm working.

# SPEAKER_01 - 03:00:33
My Open Claw agents use API tokens, completely separate. I'm running those tokens through OpenRouter, which centralizes all my API usage and makes it easy to select from hundreds of models and providers.

# SPEAKER_01 - 03:00:43
More importantly, it lets me carefully optimize which agents use which models for which tasks. You know, honestly, that optimization is probably where I spent the most time this past week.

# SPEAKER_01 - 03:00:51
Just figuring out which tasks need the power of Opus and which can run on cheaper, faster models. Still, running this team of agents is not cheap.

# SPEAKER_01 - 03:00:58
And if you've been building with the frontier models, then you already know this isn't a free ride. And from a business standpoint, if you compare the token costs to the cost of hiring multiple team members to do the work that can—and maybe should be—delegated to agents, the ROI math gets pretty compelling.

# SPEAKER_01 - 04:00:10
Now, to the question of chatting with my agents, Open Claw supports a wide range of chat tools. I started with Telegram since that was the easiest to get up and running.

# SPEAKER_01 - 04:00:17
It worked for a few days, and I was even able to set up separate Telegram bots for each agent. I'll talk about my multi-agent configuration in just a minute.

# SPEAKER_01 - 04:00:23
But after a few days on Telegram, I found the interface just wasn't comfortable, especially when agents would send me markdown-formatted content, which kind of works, kind of doesn't.

# SPEAKER_01 - 04:00:31
So again, I'm working with my agents like I tend to work with teammates. And my teams have always used Slack.

# SPEAKER_01 - 04:00:37
So I set up Slack bots for each of my agents, and that was super easy. And Slack has great markdown support, and I really like how we can use threaded replies. And that makes it easy to manage multiple agents with multiple requests and responses flying around.

# SPEAKER_01 - 04:00:48
Now, here's what made Open Claw really click for me. Instead of using it as a single agent, I set up a multi-agent configuration so that I can build an actual team of four agents.

# SPEAKER_01 - 04:00:56
Claw is my system admin, who I work with when I'm tinkering with my Open Claw system itself. Bernard is my developer. Val works on marketing tasks, and Gumbo is my general assistant.

# SPEAKER_01 - 05:00:05
Each agent runs as its own Slack bot with its own conversations. And I experimented with having them all in a group chat, which kind of works, but has some quirks.

# SPEAKER_01 - 05:00:12
So I assigned a default model to each agent: Opus for Bernard, the developer, and Claw, the system admin. That's where reasoning power really matters. And then Sonnet for Val, the marketer, and Gumbo, the assistant. That's where speed and efficiency make more sense.

# SPEAKER_01 - 05:00:23
But I often direct them to delegate parts of their work to sub-agents for tasks where I need to specify a more expensive model or a cheaper model.

# SPEAKER_01 - 05:00:30
Now, I decided to have them all share one workspace, which means they all access the same memory, and I can manage configurations and `agents.md` directives all in one place.

# SPEAKER_01 - 05:00:37
Also, my brain folder lives in this workspace, and that's where all of our work gets synced up. And if you want to hear more about my productivity system with my agents, let me know in the comments, and I'll make another video all about that.

# SPEAKER_01 - 05:00:46
Now, Open Claw has an `identity.md` file, and that's typically used to define a single agent's identity. But I use it to define multiple identities, one for each agent on my team.

# SPEAKER_01 - 05:00:55
I even use Claude and Gemini to develop unique personality traits and a visual avatar for each agent. I wanted to have fun with it. My bots are characters inspired by one of my favorite bands, Gorillaz.

# SPEAKER_01 - 06:00:04
Now, I did run into some challenges with Open Claw's built-in cron system for scheduled tasks. It was hard to associate those tasks with specific agents on my team. And so that ended up being one of the main reasons I built my own custom dashboard and task dispatching system.

# SPEAKER_01 - 06:00:15
So I quickly realized that managing my agents via chat alone was not going to cut it. I wanted to see all my scheduled tasks in one place and be able to assign them to specific agents.

# SPEAKER_01 - 06:00:23
And I wanted to track token usage so I know how much all of this is costing me. I just wanted a central dashboard where I could see the whole system at a glance.

# SPEAKER_01 - 06:00:29
So naturally, I built one. An excuse to build something, right? I used Claude Code and my Design OS process, and I had a working app in about a day.

# SPEAKER_01 - 06:00:36
It's a simple Rails app that connects to Open Claw's gateway and gives me a clean interface for managing everything. Honestly, that HQ dashboard was just the beginning.

# SPEAKER_01 - 06:00:44
Now I'm building another app for editing and reading markdown files in my brain system so that I can easily manage what my agents have access to.

# SPEAKER_01 - 06:00:51
This is what I love about this moment for builders. When a tool that I need doesn't exist yet, I just build it in a day.

# SPEAKER_01 - 06:00:56
And the most important question, and the one that I keep hearing everywhere, is what are you actually going to use your agents for?

# SPEAKER_01 - 07:00:01
So I've identified a few specific areas where my agents can fill real gaps in my business. Let's start with the content that I publish.

# SPEAKER_01 - 07:00:07
Now I only put things out when I have something to say, and that'll never change. But the truth is, so much happens inside my projects and in my conversations with other builders that never makes it to a video or a social post.

# SPEAKER_01 - 07:00:16
So I'm building systems now that let my agents observe and capture more of that work and help me share more of it across my platforms.

# SPEAKER_01 - 07:00:22
Second is development. Now I still love to spend most of my time in Claude Code and Cursor designing and architecting products. That's not going to change.

# SPEAKER_01 - 07:00:29
But I'm having Bernard, my developer agent, pick up backlog issues, track production errors, and submit PRs during times when I can't get my hands on those things.

# SPEAKER_01 - 07:00:36
Third is the glue work. This is a bottleneck that I feel every single day. Every minute that I spend project managing, or copying and pasting, or scheduling content, or documenting things, that's time that I'm not thinking, creating, or building.

# SPEAKER_01 - 07:00:47
And those tasks should be automated or delegated. And that's exactly what my general assistant, Gumbo, is for.

# SPEAKER_01 - 07:00:52
And the use case that has me most excited is reporting. So having my agents surface trends, patterns, and new ideas on a regular basis, helping me see blind spots that I wouldn't notice on my own.

# SPEAKER_01 - 08:00:02
That's the kind of insight that helps me teach ideas that actually help builders get ahead and helps me create tools that solve real problems.

# SPEAKER_01 - 08:00:08
Now I've already started assembling the building blocks: the processes for my agents to follow, the automations, the custom tooling. And I'd love to report back on a future video to show you how all that's coming together.

# SPEAKER_01 - 08:00:17
So make sure you subscribe to the channel. Now I want to be careful not to oversell Open Claw. It's still very early, very raw. And I spent more late nights than I'd like to admit just getting things configured.

# SPEAKER_01 - 08:00:25
But there's no denying the breakthrough as a concept that Open Claw has broken open here, at least in our circles of AI-pilled builders.

# SPEAKER_01 - 08:00:32
And I see this as one of those things that's worth our extra effort to be an early adopter on because systems like this are only going to become more commonplace as this year and next year play out.

# SPEAKER_01 - 08:00:40
And that gets at something that I think is a fundamental skill for us as builders in 2026. We have to be willing to explore and tinker, to figure out how new tools can help us make real progress in our business.

# SPEAKER_01 - 08:00:50
That's the value that we bring to the table. And it's one of the five essential skills that I think we need to master to go from being overwhelmed by the speed of change to actually thriving in this new environment.

# SPEAKER_01 - 08:01:00
And I cover all five in my video on going from an AI skeptic to building an unfair advantage. So right after you hit subscribe on the channel, I'll see you on that one next. Let's keep building.
