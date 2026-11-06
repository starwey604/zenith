import { mountComments, type CommentsHandle } from '../index.ts';
import './style.css';

const host = document.querySelector<HTMLElement>('#discussion')!;
const part = document.querySelector<HTMLSelectElement>('#part')!;
const clearance = document.querySelector<HTMLInputElement>('#clearance')!;
let handle: CommentsHandle;
function mount(envId?: string): void {
  handle?.destroy();
  handle = mountComments(host, { envId, getContext: () => ({
    topic: 'dock', candidate: 'rear-guided-v1', revision: 'demo-2026-11-06',
    // Deliberately canonical: no URL search string, contact information, or browser state is collected.
    pageUrl: `${location.origin}${location.pathname}`,
    part: part.value, parameters: { wireClearanceMm: Number(clearance.value) },
  }) });
}
mount();
part.addEventListener('change', () => handle.refreshContext());
clearance.addEventListener('change', () => handle.refreshContext());
document.querySelector<HTMLFormElement>('#setup')!.addEventListener('submit', event => {
  event.preventDefault();
  const value = String(new FormData(event.currentTarget as HTMLFormElement).get('endpoint') || '').trim();
  mount(value || undefined);
});
