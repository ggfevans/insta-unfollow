# Disclaimer

**Use `unfollow.js` at your own risk.**

`insta-unfollow` is an independent, unofficial tool. It is not affiliated with,
endorsed by, or connected to Instagram or Meta Platforms, Inc.

## The offline analyser is safe

`insta_unfollow.py` and `build_queue.py` are **offline and read-only**. They make
no network calls, use no Instagram API, require no login or password, and only
read a data export you downloaded yourself. Your data never leaves your computer.

## The console unfollower carries real risk

`unfollow.js` automates actions inside your logged-in session. **Automating
interactions violates Instagram's Terms of Service** and can result in:

- temporary action-blocks (hours to days where you can't follow/unfollow),
- longer feature restrictions, or
- in the worst case, account suspension.

The script tries to reduce that risk — it acts at a randomised, human-like pace,
caps how much it does per session, and halts the moment it detects an
action-block — but **no precaution can guarantee your account's safety.**

If you choose to use it:

- Start with a small cap and only ramp up over days if you see no blocks.
- Run the dry run first and confirm the targets are correct.
- Stop if you get any block and wait 24–48 hours before trying again.

## No warranty

This software is provided "as is", without warranty of any kind. The authors are
not liable for any consequence of its use, including any action taken against your
Instagram account. See [LICENSE](LICENSE).
