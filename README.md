# singlet

Write a message. It becomes a quantum circuit, is measured 1,024 times, and settles into a one-of-one result stamped on Solana. Anyone can recompute any result.

In physics a singlet is the entangled pair state where two particles share one result. The name is a single setting (`CONFIG.name`), so you can change it in one place.

**It runs on a noisy statevector simulator in the browser. It is not connected to any quantum hardware, and the site says so.** The simulator is real: it is checked against known physics (Bell state, gate identities, probability conservation). The noise model adds gate errors, readout flips and the occasional stuck qubit.

The site is one static file, `public/index.html`. There is no server and no build step to deploy.

## How a result is made

1. The circuit comes from the message, the wallet, the previous run and the edition, hashed with SHA-256.
2. The wallet signs a Memo transaction that carries those inputs. It costs the Solana network fee.
3. The shots are seeded by that transaction's **signature and slot**, which do not exist until the block lands, so nobody can try seeds for free.
4. Every result page rebuilds the circuit and all 1,024 shots in the browser from the public memo and checks the transaction on-chain (it must exist, carry that memo and be signed by the wallet the memo names).
5. Rarity is a percentile of drift from the ideal result, measured against about 3,000 reference runs per edition and qubit count (`src/cal.json`). A stuck qubit makes a run Glitched.

## What is on the site

- **Run:** solo runs with 4, 6, 8 or 10 qubits, a circuit diagram, a collapse sequence you can replay, artwork drawn from the measurements (hover it to read any outcome), and a live preview of the ideal result as you type. Without a ledger address anyone can run as a guest with no wallet.
- **Entangled pairs:** one wallet invites another, both messages build one circuit and both share the result. Accepting checks the invite on-chain, so a forged invite cannot be accepted.
- **The Forge:** six editions with different chip behaviour and a cap each, counted from the ledger. Optional token burn in the same transaction.
- **Ledger and Hall of rarity:** read straight from Solana, with filters, search and paging. The Hall ranks the rarest runs.
- **Wallet pages:** yours (with achievements and a JSON export) or any address, read-only.
- **The lab:** five experiments that run in the browser with no wallet and no network: a rotating qubit, a Bell pair, your own message with shots and noise sliders, a double slit, and a guessing game.
- **Challenge links:** share a message so a friend runs the exact same circuit and gets their own result.
- **System check:** tests the simulator, encoding, wallet detection, the Solana connection, the ledger address and the token settings, and reports what failed and why.
- A header with the page links in the middle of the top bar at every width from 801px up (compact on tablets), and on their own centred row on phones.
- Text and sections fade up into view as you scroll (off for reduced motion, and never hides anything if the browser lacks the feature).
- A living background (entangled pairs that collapse when you touch them), a sound toggle (off by default), achievements, and a wallet connection that supports the wallet standard, older wallet interfaces and silent reconnect.

## Configure

Edit the `CONFIG` block at the top of the script (in `src/build.py`, then rebuild, or directly in `public/index.html`).

| Setting | Meaning |
| --- | --- |
| `name` | The site name. |
| `rpc` | Solana RPC. The free public endpoint rate-limits browsers: use your own provider. |
| `network` | `mainnet` or `devnet`. |
| `ledgerAddress` | Any public Solana address. Every stamp includes it so the ledger can list all runs. Use a fresh address made for this project. You do not need its private key. Empty means local mode. |
| `tokenMint`, `tokenSymbol`, `tokenDecimals` | Optional token. Empty mint means anyone with a wallet can pick 4 to 10 qubits. |
| `tiers` | Balance (whole tokens) needed for each qubit count when a token is set. |
| `forgeBurn` | Whole tokens burned when forging an edition (0 for none). Burning is irreversible. |
| `x` | Link shown in the footer. |

## Before you launch

- **Test on devnet first.** Ledger listing depends on Solana indexing the ledger address when it is in a transaction but not used by any instruction. This was built from the documented behaviour of `getSignaturesForAddress` but has only been tested against a simulated network. Stamp one run on devnet and confirm it appears on the ledger page. The System check page reads the ledger address and tells you if it has no stamps yet.
- Stamp one run on mainnet with a small wallet before you announce.
- **Try your real wallets.** The wallet connection is tested with simulated wallets only. The older-wallet interface path for sending transactions is a best effort and may not work with every wallet; wallets that support the wallet standard are the supported route.
- If you set a token: confirm the mint and decimals (the System check compares them) and test a burn with a small amount.
- Use your own RPC.
- Take legal advice for your jurisdiction if the project involves a token.

## What this does not do

- No real quantum hardware. Reaching real hardware needs a server and an account with the hardware provider.
- No NFT minting. That needs a collection and a server that signs for it. Each stamp is a public on-chain record that anyone can verify.
- The ledger shows runs from the newest 100 stamps per page and pages back on request.

## Develop

```
cd src && python3 build.py          # rebuilds public/index.html
node tools/physics.js               # 19 physics and determinism checks
node tools/calibrate.js 3000        # regenerates src/cal.json (about 30 s)
pip install -r tests/requirements-test.txt && playwright install chromium
python tests/test_site.py           # 312 browser checks, about 7 minutes
```

`tests/test_site.py` uses simulated wallets and a simulated Solana network. It also runs the engine in Node and requires identical shots, tier and percentile to the browser, and it clicks every link and button on every page.

## Hosting

- **Vercel:** import the repo. `vercel.json` marks it as a static site that serves `public/`.
- **GitHub Pages:** Settings > Pages > Source: GitHub Actions. `.github/workflows/pages.yml` deploys `public/`.

No license is chosen yet: add a `LICENSE` file before publishing if you want others to reuse the code.
