# Desktop Crafting CLI bootstrap

The Crafting CLI is a small local control-plane client. It is allowed on stakeholder devices; Node, npm, pnpm, Git
checkouts, builds, tests, and source editing are not. Those remain in Crafting.

## Preferred organization rollout

For predictable access, ask IT to deploy and update `cs` through the existing device-management system:

- macOS: Jamf, Kandji, or the organization's equivalent
- Windows: Microsoft Intune or the organization's equivalent

IT should use the current package/instructions from the authenticated Crafting Web Console **Download** menu, configure
the organization's Crafting server URL when required, place `cs` on the user PATH, and verify `cs version`. Do not copy
an old CI-only Linux download URL or invent macOS/Windows artifact names.

The desktop app may need to restart after installation so Claude Desktop or Codex inherits the updated PATH.

## Agent-guided fallback

At the start of every experiment:

```sh
cs version
cs login --status
```

If `cs` is missing:

1. Say: “The Crafting helper is not installed yet. It is the only local helper this workflow needs; all design tools and
   code still run in Crafting. May I guide the one-time installation?”
2. Detect macOS versus Windows without asking the user technical questions.
3. Direct the user to sign in to the organization's Crafting Web Console and open **Download**. Use the current
   platform-specific command/package shown there.
4. Ask permission before executing that installation command from the desktop agent. Never use an unofficial mirror,
   an unversioned guessed URL, or instructions copied from a different operating system.
5. If the OS requests administrator approval, let the user complete the native prompt. Never ask for their password or
   paste it into a command/chat.
6. Verify `cs version`. If the executable was installed but is not visible to the current desktop app, find its official
   install location only to confirm installation, then ask the user to restart the desktop app. Do not modify broad shell
   startup files speculatively.
7. Configure the server URL only when the Crafting Download/onboarding instructions or organization admin provide it:

   ```sh
   cs config set server_url <organization-Crafting-URL>
   ```

8. Run `cs login --if-needed`. The CLI prints a browser login URL; the user completes authentication in their browser.
   Do not use service-account tokens for stakeholder desktops and never ask for a token in chat.
9. Verify `cs info` before creating or changing a sandbox.

Crafting's current macOS onboarding warns against downloading the binary directly in a browser because quarantine can
block it. Follow the Web Console's installation command instead. On Windows, use the current Windows instructions from
the same Download menu rather than translating Unix commands.

## Failure handling

- **No Download access:** ask the Crafting organization admin or IT to provision the user; do not fetch a binary from
  elsewhere.
- **Unsupported architecture or OS policy:** stop and route to IT with the detected OS, architecture, and exact error.
- **Login opens the wrong organization:** do not create a sandbox; confirm the Diversio Crafting server/organization.
- **Desktop cannot see a successful install:** restart the desktop app first. Reinstall only after confirming the binary
  is actually absent.
- **Upgrade requested:** use current Crafting instructions or managed deployment. Do not silently replace a working CLI
  during an experiment.

Record only the `cs` version and authentication success/failure in the conversation. Do not expose session files,
credentials, login URLs, or tokens.
