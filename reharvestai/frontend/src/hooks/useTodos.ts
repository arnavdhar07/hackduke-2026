'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTodos, completeTodo } from '@/lib/api';

export function useTodos() {
  const qc = useQueryClient();
  const { data: todos = [], isLoading } = useQuery({
    queryKey: ['todos'],
    queryFn: getTodos,
    refetchInterval: 30_000,
  });
  const { mutate: markDone } = useMutation({
    mutationFn: completeTodo,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['todos'] }),
  });
  const pending = todos.filter(t => t.status === 'pending');
  return { todos, pending, markDone, isLoading };
}
