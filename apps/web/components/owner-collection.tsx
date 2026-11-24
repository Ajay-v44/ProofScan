"use client";

import { api } from "@proofscan/api-client";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Button } from "./ui/button";

const pageSize = 30;

export function useOwnerCollection<T extends { id: string }>(
  path: string,
  key: string,
  owner: string | undefined,
  options: { enabled?: boolean; pollInterval?: number } = {},
) {
  const query = useInfiniteQuery({
    queryKey: [key, owner],
    enabled: !!owner && options.enabled !== false,
    initialPageParam: "",
    queryFn: ({ pageParam }) => api<T[]>(path + (pageParam ? "?before=" + encodeURIComponent(pageParam) : "")),
    getNextPageParam: page => page.length === pageSize ? page.at(-1)?.id : undefined,
    refetchInterval: ({ state }) => (state.data?.pages.length ?? 0) <= 1 ? options.pollInterval : false,
  });

  return {
    items: query.data?.pages.flat() ?? [],
    error: query.error,
    isPending: query.isPending,
    isFetching: query.isFetching,
    isFetchingNextPage: query.isFetchingNextPage,
    hasNextPage: query.hasNextPage,
    fetchNextPage: query.fetchNextPage,
    refetch: query.refetch,
  };
}

export function LoadMore({ onClick, busy, loading }: {
  onClick: () => void;
  busy: boolean;
  loading: boolean;
}) {
  return <Button variant="outline" disabled={busy} onClick={onClick}>{loading ? "Loading…" : "Load more"}</Button>;
}
