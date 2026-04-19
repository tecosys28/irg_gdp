# Recovery guide for families

A plain-language explanation of what to do if you need to recover an IRG
wallet on behalf of a family member who has passed away, become unable to
manage their affairs, or lost access.

This guide is intentionally non-technical. If at any point anything on
this page does not match what you are actually seeing in the IRG app,
stop and contact the IRG Ombudsman office — do not guess.

## First, a few things IRG will never ask you for

IRG staff, the IRG Ombudsman, and anyone acting on their behalf will
**never** ask you for:

- the deceased person's 15-word recovery phrase
- the deceased person's wallet password
- their login password or OTP codes
- payment to process a recovery request

If anyone asks for any of these things, it is a scam. Report it.

## What IRG keeps, and what it does not

- We keep: the wallet address, a hash of the wallet password (so it can
  be checked but never read), a hash of the 15-word recovery phrase
  (same), and the list of nominees the wallet holder registered.
- We do not keep: the password itself, the recovery phrase itself, the
  private key, or anything else that would let us move assets on behalf
  of a user. This is intentional. It is what makes the wallet truly
  theirs.

Because we cannot reset a password for you, we have a formal recovery
process for the cases where something has gone wrong.

## The three recovery paths

There are three ways an IRG wallet can be recovered. You pick the one
that matches your situation.

### 1. Self-recovery

**When to use:** the person is alive, well, and in control, but has
lost their phone or forgotten their password. They have their 15-word
recovery phrase written down somewhere.

**What to do:** install the IRG app on a new phone, open it, and choose
"Recover my wallet". You will be asked for the 15 words. If the words
match, the wallet is rebound to the new phone. Transactions are paused
for 48 hours as a cooling-off period.

### 2. Social recovery (nominee-assisted)

**When to use:** the person is alive but cannot get back in — lost
recovery phrase, lost phone, forgotten password all at the same time.
The wallet holds a small amount (under ₹50,000 worth). At least two of
the registered nominees are available to help.

**What to do:** one of the nominees opens the IRG app and chooses
"Recover someone else's wallet -> social recovery". They enter the
original wallet address, their own wallet address, and explain the
situation. The original owner is notified through every channel we
have — phone call, SMS, WhatsApp, email, push notification. If the
owner does not cancel the request within 7 days, the other nominees
are asked to co-sign. Once enough signatures arrive, assets move.

### 3. Trustee / Ombudsman recovery

**When to use:** this is the path for serious cases:
- death
- mental incapacity
- prolonged incapacity after an accident
- legal dispute between possible heirs
- any wallet holding assets over ₹50,000 worth that cannot use
  self or social recovery

**What to do:**

1. **Gather documents.** Depending on the situation you may need:
   - Death certificate
   - Legal heir certificate OR succession certificate
   - Court-issued letter of administration
   - Probated will
   - Medical incapacity certificate
   - Your own KYC documents (Aadhaar, PAN)

   You do not need all of these. The Ombudsman will tell you what
   specifically they need for your case.

2. **File the case.** From the IRG login screen choose "Recover
   someone else's wallet -> trustee/ombudsman path". Upload the
   documents. Explain your relationship to the wallet holder.

3. **Public notice period (30 days).** A public on-chain notice is
   posted so any other claimant, objection, or competing claim can be
   heard. The original wallet holder (if alive) is also notified
   repeatedly — this protects them if the claim is false.

4. **Ombudsman review.** The IRG Ombudsman will review everything.
   They may ask questions, ask for additional documents, hold a hearing
   (in person, by video, or in writing — whichever works for you).
   Recovery is not a rubber stamp: if the Ombudsman thinks the
   documents do not support the claim, or that there is a dispute that
   really belongs in a civil court, they will say so.

5. **Order.** The Ombudsman issues a reasoned written Order. If
   approved, assets transfer to the wallet you control.

6. **Reversibility window (90 days).** For 90 days after the transfer,
   the Order can be reversed if a civil court subsequently rules
   differently. This is protection against honest mistakes — it does
   not affect straightforward cases.

## How long does it take?

- Self-recovery: minutes. 48-hour cooling-off before transactions.
- Social recovery: 7 days cooling-off + however long the nominees take
  to sign.
- Trustee / Ombudsman: 30 days public notice + Ombudsman review time,
  typically another 2–6 weeks depending on complexity.

We know this feels slow, especially in a time of grief. The waiting
period is what makes the system safe against fraud: it gives a real
owner time to object if a recovery claim is wrong.

## Who pays for it?

Nothing. Filing a recovery case is free. The Ombudsman is funded from
the IRG Super Corpus Fund. If anyone charges you money to "speed up"
your case, it is a scam.

## If something does not match this guide

Contact the IRG Ombudsman office. Never act on instructions from
anyone who contacts you unsolicited claiming to be from IRG, even if
they seem to know details about your family member's wallet.

The Ombudsman office exists precisely so that families with no prior
IRG experience have a real human to talk to. There is no charge.

## One last thing

If you are reading this because someone you loved has died, we are
sorry for your loss. We know this is a difficult time to be filling
out forms. Take it slowly. The assets are safe. The system is designed
to wait for you.
