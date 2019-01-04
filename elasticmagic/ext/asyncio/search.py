from ...search import BaseSearchQuery


class AsyncSearchQuery(BaseSearchQuery):
    """Asynchronous version of the :class:`.SearchQuery`
    """

    async def get_result(self):
        if self._cached_result is not None:
            return self._cached_result

        self._cached_result = await self._index_or_cluster.search(
            self, **self._prepare_search_params()
        )
        return self._cached_result

    async def count(self):
        return (
            await self._index_or_cluster.count(
                self, **self._prepare_search_params()
            )
        ).count

    async def exists(self):
        return (await self._exists_query().get_result()).total >= 1

    async def _iter_result_async(self):
        return self._iter_result(await self.get_result())

    def __await__(self):
        return self._iter_result_async().__await__()

    async def _getitem_async(self, k):
        clone, is_slice = self._prepare_slice(k)
        if is_slice:
            return list(await clone)
        else:
            return list(await clone)[0]

    def __getitem__(self, k):
        return self._getitem_async(k)