import { ContractViolation } from "./errors";

interface GraphQLResponse<T> {
  data?: T;
  errors?: Array<{ message: string; extensions?: { code?: string } }>;
}

/**
 * Minimal typed GraphQL client.
 *
 * Deliberately not Apollo Client: this app has four read-only queries and no
 * cache-invalidation problem, so a 30-line fetch wrapper carries less weight
 * than a client library two juniors would also have to learn.
 */
export async function gql<
  TData,
  TVars extends Record<string, unknown> = Record<string, never>,
>(query: string, variables?: TVars): Promise<TData> {
  const res = await fetch("/graphql", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query, variables }),
  });

  if (!res.ok) {
    throw new Error(`GraphQL transport failed: HTTP ${res.status}`);
  }

  const body = (await res.json()) as GraphQLResponse<TData>;

  if (body.errors?.length) {
    const first = body.errors[0]!;
    throw new Error(`${first.extensions?.code ?? "ERROR"}: ${first.message}`);
  }

  if (!body.data) {
    throw new ContractViolation("GraphQL response had neither data nor errors");
  }

  return body.data;
}
