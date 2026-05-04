---
title: Protecting Our Own Tenant in a Multi-Tenant SaaS
slug: protecting-our-own-tenant-in-a-multi-tenant-saas
summary: How Diversio treats its own tenant inside Optimo as the hardest one to reach, using layered controls across Django admin, approvals, Postgres RLS, IAM, and automation.
publishDate: 2025-11-24
author:
  name: Ashwini Chaudhary
  url: https://ashwch.com
tags:
  - engineering
  - security
  - django
  - multi-tenant
  - saas
sourceType: repost
sourceSiteName: ashwch.com
sourceUrl: https://ashwch.com/protecting-our-own-tenant-in-a-multi-tenant-saas/
canonicalUrl: https://ashwch.com/protecting-our-own-tenant-in-a-multi-tenant-saas/
---

*This post was originally published on [ashwch.com](https://ashwch.com/protecting-our-own-tenant-in-a-multi-tenant-saas/).*

If your own company is a tenant in your own product, it should be the hardest one to access, not the easiest.

At Diversio, one of the products we build is Optimo, a multi-tenant SaaS that helps HR and people teams work with sensitive employee and organizational data. Most Optimo organizations belong to customers. One belongs to us. That internal Diversio org inside Optimo holds our own employee and company data, and our engineers and Client Success team use the same product surfaces to support both.

[Read the full post on ashwch.com →](https://ashwch.com/protecting-our-own-tenant-in-a-multi-tenant-saas/)
