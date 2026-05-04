---
title: Managing Context Metadata in Django-PGHistory
slug: managing-context-metadata-django-pghistory
summary: How Diversio solved metadata leakage between contexts in django-pghistory for cleaner, more accurate audit trails, and what other Django teams can learn from the approach.
publishDate: 2025-04-02
author:
  name: Ashwini Chaudhary
  url: https://ashwch.com
tags:
  - engineering
  - django
  - python
  - audit-trails
sourceType: repost
sourceSiteName: ashwch.com
sourceUrl: https://ashwch.com/managing-context-metadata-django-pghistory-solving-persistence-problem/
canonicalUrl: https://ashwch.com/managing-context-metadata-django-pghistory-solving-persistence-problem/
---

*This post was originally published on [ashwch.com](https://ashwch.com/managing-context-metadata-django-pghistory-solving-persistence-problem/).*

Learn how `pghistory.context` works and some of its gotchas that we faced at Diversio (thanks to Amal Raj B R who identified the issue), and how we adjusted our approach to avoid saving context metadata that is not relevant to the current business logic but is being carried over from a parent context.

[Read the full post on ashwch.com →](https://ashwch.com/managing-context-metadata-django-pghistory-solving-persistence-problem/)
