import asyncio
import random

import zmq
import zmq.asyncio


async def handle_client(socket, identity, message):
    print(f"Received request from {identity}: {message.decode()}")
    # 随机延时 0 到 3 秒
    await asyncio.sleep(random.uniform(0, 3))
    task_id = random.randint(1000, 9999)  # 随机生成一个任务 ID
    await socket.send_multipart([identity, f"Task ID: {task_id}".encode()])
    print(f"Sent Task ID {task_id} to {identity}")


async def server():
    context = zmq.asyncio.Context()
    socket = context.socket(zmq.ROUTER)
    socket.bind("tcp://*:5555")

    while True:
        try:
            identity, message = await socket.recv_multipart()
            asyncio.create_task(handle_client(socket, identity, message))
        except Exception as e:
            print(f"An error occurred: {e}")
            break

    socket.close()
    context.term()


if __name__ == "__main__":
    asyncio.run(server())
