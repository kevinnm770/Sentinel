# Sentinel Domain Specification
Version: 1.0.0
Status: Draft
Project: Sentinel
Authors: Youser Núñez, Kevin Naranjo
Lead Architect: Daemon

---

# 1. Purpose

## 1.1 Objective

This document defines the official business domain of Sentinel.

Its purpose is to establish a single source of truth for every business rule, entity,
relationship and workflow inside the project.

Any modification to the domain must be reflected in this document before being
implemented in code.

The software architecture, database design and implementation must always follow
this specification.

---

# 2. Vision

Sentinel is a competitive team management platform built around Discord.

Unlike traditional Discord bots that execute isolated commands,
Sentinel models the complete lifecycle of competitive organizations.

The project is designed to support multiple Discord servers while keeping every
organization completely isolated.

Sentinel is not a reminder bot.

Sentinel is an organizational platform.

---

# 3. Mission

Provide competitive communities with a centralized platform capable of managing:

• Teams

• Coaches

• Players

• Training schedules

• Attendance

• Notifications

• Voice sessions

• Statistics

• Future tournament support

The platform should minimize administrative work while maximizing organization.

---

# 4. Design Philosophy

Every architectural decision inside Sentinel follows five principles.

## 4.1 Separation of Concerns

Every component must have exactly one responsibility.

Discord should never contain business logic.

Business logic should never manipulate SQL directly.

Repositories should never communicate with Discord.

---

## 4.2 Configuration over Code

Sentinel must never contain hardcoded server information.

Everything should be configurable by server administrators.

Examples:

Roles

Channels

Schedules

Languages

Timezone

Permissions

---

## 4.3 Scalability

Every module should be capable of supporting thousands of Discord servers.

No implementation should assume the existence of only one Guild.

---

## 4.4 Maintainability

Code readability is more important than code brevity.

The project should remain understandable after years of development.

---

## 4.5 Domain First

Business rules define the software.

The software never defines the business.

---

# 5. Ubiquitous Language

Every developer contributing to Sentinel must use the same terminology.

Never invent alternative names.

The following terms are official.

Guild

A Discord Server using Sentinel.

Team

A competitive roster inside one Guild.

Coach

Person responsible for one or more teams.

Player

Competitive member belonging to one or more teams.

Training

A scheduled practice session.

Schedule

Recurring weekly configuration that defines when trainings occur.

Attendance

Record indicating whether a player participated in a training.

Reminder

Automatic notification generated before a training begins.

Voice Session

Tracking information generated while players are connected to voice channels.

Administrator

Guild owner or delegated administrator.

Manager

Person responsible for organizing competitive teams.

---

# 6. Actors

Sentinel recognizes five types of actors.

## Administrator

Highest authority.

Responsibilities

Configure Sentinel

Assign managers

Configure permissions

Manage integrations

Configure channels

---

## Manager

Organizes the competitive structure.

Responsibilities

Create teams

Assign coaches

Register players

Configure schedules

Review reports

---

## Coach

Responsible for one or more teams.

Responsibilities

Schedule trainings

Review attendance

Manage roster

Confirm practice completion

---

## Player

Competitive participant.

Responsibilities

Receive reminders

Join voice channel

Confirm attendance

Participate in trainings

---

## Sentinel

Autonomous actor.

Responsibilities

Monitor schedules

Generate reminders

Track attendance

Store statistics

Execute scheduled jobs

---

# 7. Domain Overview

Sentinel is composed of independent bounded contexts.

Guild Management

↓

Team Management

↓

Training Management

↓

Attendance

↓

Notifications

↓

Statistics

Each context owns its own business rules.

Communication between contexts occurs only through Services.

---

# 8. Core Entities

## Guild

Represents one Discord Server.

A Guild is the root container for every object in Sentinel.

Without a Guild nothing else can exist.

Attributes

guild_id

name

language

timezone

created_at

is_active

Relationships

Guild owns Teams

Guild owns Managers

Guild owns Settings

Guild owns Schedules

---

## Team

Represents a competitive roster.

Every Team belongs to exactly one Guild.

Attributes

team_id

guild_id

name

description

role_id

voice_channel_id

text_channel_id

coach_id

created_at

active

Relationships

Belongs to Guild

Contains Players

Owns Trainings

Owns Attendance

---

## Player

Represents one competitive player.

A Discord member may belong to multiple teams.

Attributes

player_id

discord_user_id

nickname

join_date

status

Relationships

Member of Team

Participates in Training

Generates Attendance

---

## Coach

Represents a competitive coach.

A Coach may supervise multiple teams.

Attributes

coach_id

discord_user_id

name

status

Relationships

Owns Teams

Creates Trainings

Reviews Attendance

---

## Training

Represents one practice session.

Attributes

training_id

team_id

scheduled_date

start_time

end_time

status

created_by

Relationships

Belongs to Team

Generates Attendance

Triggers Reminders

Creates Voice Session

---

## Schedule

Recurring weekly configuration.

Attributes

schedule_id

team_id

day_of_week

start_time

end_time

enabled

timezone

Relationships

Creates Trainings

Generates Reminders

---

## Reminder

Automatic notification.

Attributes

reminder_id

training_id

minutes_before

message

status

sent_at

Relationships

Belongs to Training

---

## Attendance

Stores participation information.

Attributes

attendance_id

training_id

player_id

joined_at

left_at

confirmed

duration

Relationships

Belongs to Training

Belongs to Player

---

## Voice Session

Represents Discord voice activity.

Attributes

session_id

voice_channel

started_at

ended_at

participants

Relationships

Belongs to Training

Produces Attendance

---

# 9. Entity Relationships

Guild

└── Teams

├── Players

├── Coach

├── Trainings

│

├── Attendance

│

└── Notifications
  