"""StorageServer implementation - ZMQ server for remote storage access."""

import asyncio
import pickle
from typing import Any, List, Optional, Tuple, Union

import zmq
from loguru import logger

from qulab.sys.rpc.zmq_socket import ZMQContextManager

from .local import LocalStorage


class StorageServer:
    """Storage server - ZMQ RPC implementation.

    Provides remote access to a LocalStorage instance via ZMQ.
    """

    def __init__(
        self,
        storage: LocalStorage,
        host: str = "127.0.0.1",
        port: int = 6789,
    ):
        """Initialize storage server.

        Args:
            storage: LocalStorage instance to serve
            host: Host address to bind to
            port: Port to listen on
        """
        self.storage = storage
        self.host = host
        self.port = port
        self._running = False
        self._socket = None

    @property
    def address(self) -> str:
        """Get the server address."""
        return f"tcp://{self.host}:{self.port}"

    async def handle(self, message: dict) -> Any:
        """Handle a request message.

        Args:
            message: Request message dictionary

        Returns:
            Response data
        """
        method = message.get("method")
        handler = getattr(self, f"handle_{method}", None)

        if handler is None:
            return {"error": f"Unknown method: {method}"}

        try:
            # Remove method from kwargs
            kwargs = {k: v for k, v in message.items() if k != "method"}
            return await handler(**kwargs)
        except Exception as e:
            logger.exception(f"Error handling {method}")
            return {"error": str(e)}

    # Document handlers
    async def handle_document_create(
        self,
        name: str,
        data: dict,
        state: str = "unknown",
        tags: Optional[list] = None,
        script: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> int:
        """Create a new document."""
        ref = self.storage.create_document(
            name=name,
            data=data,
            state=state,
            tags=tags or [],
            script=script,
            **(meta or {}),
        )
        return ref.id

    async def handle_document_get(self, id: int) -> dict:
        """Get a document."""
        doc = self.storage.get_document(id)
        return doc.to_dict()

    async def handle_document_get_data(self, id: int) -> dict:
        """Get document data."""
        doc = self.storage.get_document(id)
        return doc.data

    async def handle_document_query(
        self,
        name: Optional[str] = None,
        tags: Optional[list] = None,
        state: Optional[str] = None,
        before: Optional[str] = None,
        after: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple:
        """Query documents."""
        from datetime import datetime

        # Parse datetime strings
        before_dt = datetime.fromisoformat(before) if before else None
        after_dt = datetime.fromisoformat(after) if after else None

        total = self.storage.count_documents(
            name=name, tags=tags, state=state, before=before_dt, after=after_dt
        )
        results = list(
            self.storage.query_documents(
                name=name,
                tags=tags,
                state=state,
                before=before_dt,
                after=after_dt,
                offset=offset,
                limit=limit,
            )
        )
        return total, [{"id": r.id, "name": r.name} for r in results]

    async def handle_document_count(
        self,
        name: Optional[str] = None,
        tags: Optional[list] = None,
        state: Optional[str] = None,
        before: Optional[str] = None,
        after: Optional[str] = None,
    ) -> int:
        """Count documents."""
        from datetime import datetime

        before_dt = datetime.fromisoformat(before) if before else None
        after_dt = datetime.fromisoformat(after) if after else None

        return self.storage.count_documents(
            name=name, tags=tags, state=state, before=before_dt, after=after_dt
        )

    async def handle_document_delete(self, id: int) -> bool:
        """Delete a document."""
        from .local import DocumentRef

        ref = DocumentRef(id, self.storage)
        return ref.delete()

    # Document tag editing handlers
    async def handle_document_add_tags(self, id: int, tags: list) -> bool:
        """Add tags to a document."""
        self.storage.document_add_tags(id, tags)
        return True

    async def handle_document_remove_tags(self, id: int, tags: list) -> bool:
        """Remove tags from a document."""
        self.storage.document_remove_tags(id, tags)
        return True

    async def handle_document_set_tags(self, id: int, tags: list) -> bool:
        """Set tags for a document (replace all)."""
        self.storage.document_set_tags(id, tags)
        return True

    # Dataset handlers
    async def handle_dataset_create(
        self,
        name: str,
        description: dict,
        config: Optional[dict] = None,
        script: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> int:
        """Create a new dataset."""
        ref = self.storage.create_dataset(name, description, config=config, script=script, tags=tags)
        return ref.id

    async def handle_dataset_get(self, id: int) -> dict:
        """Get dataset info."""
        ds = self.storage.get_dataset(id)
        return ds.to_dict()

    async def handle_dataset_query(
        self,
        name: Optional[str] = None,
        tags: Optional[list] = None,
        before: Optional[str] = None,
        after: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple:
        """Query datasets."""
        from datetime import datetime

        before_dt = datetime.fromisoformat(before) if before else None
        after_dt = datetime.fromisoformat(after) if after else None

        total = self.storage.count_datasets(
            name=name, tags=tags, before=before_dt, after=after_dt
        )
        results = list(
            self.storage.query_datasets(
                name=name,
                tags=tags,
                before=before_dt,
                after=after_dt,
                offset=offset,
                limit=limit,
            )
        )
        return total, [{"id": r.id, "name": r.name} for r in results]

    async def handle_dataset_count(
        self,
        name: Optional[str] = None,
        tags: Optional[list] = None,
        before: Optional[str] = None,
        after: Optional[str] = None,
    ) -> int:
        """Count datasets."""
        from datetime import datetime

        before_dt = datetime.fromisoformat(before) if before else None
        after_dt = datetime.fromisoformat(after) if after else None

        return self.storage.count_datasets(
            name=name, tags=tags, before=before_dt, after=after_dt
        )

    async def handle_dataset_append(
        self, id: int, position: tuple, data: dict
    ) -> bool:
        """Append data to a dataset."""
        ds = self.storage.get_dataset(id)
        ds.append(position, data)
        ds.flush()
        return True

    async def handle_dataset_delete(self, id: int) -> bool:
        """Delete a dataset."""
        from .local import DatasetRef

        ref = DatasetRef(id, self.storage)
        return ref.delete()

    # Dataset tag editing handlers
    async def handle_dataset_add_tags(self, id: int, tags: list) -> bool:
        """Add tags to a dataset."""
        self.storage.dataset_add_tags(id, tags)
        return True

    async def handle_dataset_remove_tags(self, id: int, tags: list) -> bool:
        """Remove tags from a dataset."""
        self.storage.dataset_remove_tags(id, tags)
        return True

    async def handle_dataset_set_tags(self, id: int, tags: list) -> bool:
        """Set tags for a dataset (replace all)."""
        self.storage.dataset_set_tags(id, tags)
        return True

    # Array handlers
    async def handle_array_getitem(
        self, dataset_id: int, key: str, index: tuple
    ) -> Any:
        """Get an array item."""
        ds = self.storage.get_dataset(dataset_id)
        arr = ds.get_array(key)
        return arr[index]

    async def handle_array_getitem_slice(
        self, dataset_id: int, key: str, slices: list
    ) -> Any:
        """Get a sliced array.

        Args:
            dataset_id: Dataset ID
            key: Array key
            slices: Serialized slice parameters from client

        Returns:
            Sliced array data
        """
        import numpy as np

        # Deserialize slice parameters
        slice_tuple = []
        for s in slices:
            if s.get("type") == "slice":
                slice_tuple.append(slice(s.get("start"), s.get("stop"), s.get("step")))
            elif s.get("type") == "int":
                slice_tuple.append(s.get("value"))
            elif s.get("type") == "ellipsis":
                slice_tuple.append(...)
            else:
                slice_tuple.append(s.get("value"))

        slice_tuple = tuple(slice_tuple)

        ds = self.storage.get_dataset(dataset_id)
        arr = ds.get_array(key)

        # Apply slicing on server side - only transfer the sliced data
        result = arr[slice_tuple]

        # Convert numpy arrays to lists for serialization
        if isinstance(result, np.ndarray):
            return result.tolist()
        return result

    async def handle_array_iter(
        self, dataset_id: int, key: str, start: int = 0, count: int = 100
    ) -> list:
        """Iterate over array items."""
        ds = self.storage.get_dataset(dataset_id)
        arr = ds.get_array(key)
        arr.flush()

        results = []
        for i, item in enumerate(arr.iter()):
            if i < start:
                continue
            if len(results) >= count:
                break
            results.append(item)
        return results

    async def run(self):
        """Run the server."""
        self._running = True
        logger.info(f"Starting storage server on {self.address}")
        logger.info(f"Data path: {self.storage.base_path}")

        async with ZMQContextManager(
            zmq.ROUTER, bind=self.address
        ) as sock:
            while self._running:
                try:
                    # Use asyncio.wait_for to allow checking _running periodically
                    identity, msg = await asyncio.wait_for(
                        sock.recv_multipart(), timeout=1.0
                    )
                    message = pickle.loads(msg)
                    response = await self.handle(message)
                    await sock.send_multipart(
                        [identity, pickle.dumps(response)]
                    )
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.exception("Error in server loop")

    def stop(self):
        """Stop the server."""
        self._running = False
        logger.info("Storage server stopping...")

    def run_sync(self):
        """Run the server synchronously."""
        asyncio.run(self.run())
