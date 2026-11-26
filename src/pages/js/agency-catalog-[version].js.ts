import { agencyCatalogScript, agencyCatalogVersion } from '../../lib/agency-catalog';

export function getStaticPaths() {
  return [{ params: { version: agencyCatalogVersion } }];
}

export function GET() {
  return new Response(agencyCatalogScript, {
    headers: { 'Content-Type': 'application/javascript; charset=utf-8' },
  });
}
