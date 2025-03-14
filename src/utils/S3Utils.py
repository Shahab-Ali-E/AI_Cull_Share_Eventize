import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError
from fastapi import HTTPException,status
from concurrent.futures import ThreadPoolExecutor
import asyncio

from utils.CustomExceptions import FolderAlreadyExistsException

class S3Utils:
    """
    Initializes the S3Utils class with AWS credentials and bucket information.

    Args:
        aws_region (str): The AWS region where the S3 bucket is located.
        aws_access_key_id (str): The AWS access key ID.
        aws_secret_access_key (str): The AWS secret access key.
        bucket_name (str): The name of the S3 bucket.
    """
    def __init__(self, aws_region, aws_access_key_id, aws_secret_access_key, bucket_name, aws_endpoint_url):
        self.client = boto3.client(
            service_name="s3",
            endpoint_url=aws_endpoint_url,
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            config=boto3.session.Config(max_pool_connections=50)
        )
        self.bucket_name = bucket_name
        self.transfer_config = TransferConfig(
                                                multipart_threshold=1024 * 1024* 5,  # 5 mb
                                                max_concurrency=10,                  # 10 threads
                                                multipart_chunksize=1024 *1024 * 5, # 5 mb chunks
                                                use_threads=True                     # Multi-threading enabled
                                            )
        self.executor = ThreadPoolExecutor()
    
    #It check if that folder already exsists which you want to create
    async def folder_exists(self, folder_key):
        """
        Checks if a folder exists in the specified S3 bucket.
        Args:
            folder_key (str): The S3 key of the folder to check.
        Returns:
            bool: True if the folder exists, False otherwise.
        Raises:
            HTTPException: If there is an error checking the folder existence.
        """
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda:self.client.list_objects_v2(
                    Bucket=self.bucket_name, 
                    Prefix=folder_key, 
                    Delimiter='/'
                )
            )

            # Check if the folder exists in either Contents or CommonPrefixes
            if response.get('Contents'):
                return True
            if response.get('CommonPrefixes'):
                return True
            
            return False
        except ClientError as e:
            raise HTTPException(f"Unable to check folder existence: {e}")
    
    #It create an object like folder/uplaod images etc in the bucket
    async def create_object(self, folder_key):
        """
        Creates an object (folder or file) in the specified S3 bucket.

        Args:
            folder_key (str): The S3 key of the folder or object to create.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.executor,
            lambda:self.client.put_object(
                Bucket=self.bucket_name, 
                Key=folder_key
            )   
        )

    # async def rollback_uploaded_images(self, folder_key):
    #     """
    #     Deletes all uploaded images inside a folder from an AWS S3 bucket asynchronously.

    #     Args:
    #         folder_key (str): The key of the folder to delete from the S3 bucket.

    #     Returns:
    #         tuple: A dictionary with a success or failure message and an HTTP status code (`HTTP_200_OK` or `HTTP_400_BAD_REQUEST`).

    #     Raises:
    #         Exception: Raises a detailed error message if a `ClientError` occurs during deletion.

    #     Description:
    #         Uses the boto3 `rollback_uploaded_images` function to delete an S3 all uploaded images asynchronously. The operation is offloaded to an executor to avoid blocking the event loop. It checks the response status to determine success or failure.
    #     """
    #     loop = asyncio.get_running_loop()
    #     # Delete a single object and return
    #     try:
    #         # Delete a single object and return
    #         response = await loop.run_in_executor(
    #             self.executor,
    #             lambda: self.client.delete_object(
    #                 Bucket=self.bucket_name,
    #                 Key=file_key
    #             )
    #         )
    #         # Check for successful deletion
    #         if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 204:
    #             return {'message': 'Deleted successfully'}, status.HTTP_200_OK
    #         else:
    #             return {'message': 'Failed to delete object'}, status.HTTP_400_BAD_REQUEST
    #     except ClientError as e:
    #         # Raise an exception with a detailed error message
    #         raise Exception(f"ClientError during S3 object deletion: {str(e)}")
        

    async def delete_object(self, folder_key, rollback=False):
        """
        Deletes an object or folder and its contents from the S3 bucket.
        Args:
            folder_key (str): The S3 key of the folder or object to delete.
        Returns:
            dict: The response from the S3 delete operation.
        Raises:
            HTTPException: If there is an error deleting the folder.
        """
        try:
            # List all objects under the specified prefix (folder)
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda:self.client.list_objects_v2(
                    Bucket=self.bucket_name, 
                    Prefix=folder_key,
                ) 
            )

            # Check if there are objects to delete
            if 'Contents' in response:
                delete_keys = [{'Key':obj['Key']} for obj in response['Contents']]
                if rollback:
                    #Delete only content of folder
                    await loop.run_in_executor(
                        self.executor,
                        lambda:self.client.delete_objects(
                            Bucket=self.bucket_name,
                            Delete={'Objects': delete_keys[1:]}
                        )
                    )
                else:
                    #Delete full folder with it's objects
                    await loop.run_in_executor(
                        self.executor,
                        lambda:self.client.delete_objects(
                            Bucket=self.bucket_name,
                            Delete={'Objects': delete_keys}
                        )
                    )
                return {"message": "Objects deleted successfully"}, status.HTTP_204_NO_CONTENT
            else:
                return {"message":"No objects found to delete in S3"}, status.HTTP_404_NOT_FOUND

        except ClientError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unable to delete folder: {e}")
        
        
    #It is use to create folder when all images are ready to cull and user starts culling
    async def create_folders_for_culling(self, root_folder, main_folder, images_before_cull_folder, blur_img_folder, closed_eye_img_folder, duplicate_img_folder, fine_collection_img_folder):
        """
        Creates a set of folders in S3 for image culling.

        Args:
            root_folder (str): The root folder under which the main and other folders will be created.
            main_folder (str): The main folder for storing images.
            images_before_cull_folder (str): The folder for storing images before culling.
            blur_img_folder (str): The folder for storing blurred images.
            closed_eye_img_folder (str): The folder for storing images with closed eyes.
            duplicate_img_folder (str): The folder for storing duplicate images.
            fine_collection_img_folder (str): The folder for storing the final selection of images.

        Raises:
            Exception: If the main folder already exists.
        """
        root_folder = f'{root_folder}/'
        main_folder = f'{root_folder}{main_folder}/'
        
        if not await self.folder_exists(root_folder):
            self.create_object(root_folder)
        
        if await self.folder_exists(main_folder):
            raise FolderAlreadyExistsException(f'Main folder "{main_folder}" already exists.')
        else:
            await self.create_object(main_folder)

        #creating folder here
        for folder in [images_before_cull_folder, blur_img_folder, closed_eye_img_folder, duplicate_img_folder, fine_collection_img_folder]:
            await self.create_object(f'{main_folder}{folder}/')
    

    #It is use to create event folder for smart share where user uploads images
    async def create_folders_for_smart_share(self, root_folder, event_name):
        """
        Creates a folder structure for event-based image sharing in S3.

        Args:
            root_folder (str): The root folder under which the event folder will be created.
            event_name (str): The name of the event folder.

        Raises:
            Exception: If the event folder already exists.
        """
        root_folder = f'{root_folder}/'
        event_name = f'{root_folder}{event_name}/'

        if not await self.folder_exists(root_folder):
            self.create_object(root_folder)
        
        if await self.folder_exists(event_name):
            raise FolderAlreadyExistsException(f'Event with name "{event_name}" already exists.')
            
        else:
            await self.create_object(event_name)
        
        
    #This will upload the prdicted images to right folder like blur goes in blur_image_folder and vice versa
    async def upload_smart_cull_images(self, root_folder, main_folder, upload_image_folder, image_data, filename):
        """
        Uploads an image to a specific folder in S3.

        Args:
            root_folder (str): The root folder under which the main and upload folders are located.
            main_folder (str): The main folder containing the upload folder.
            upload_image_folder (str): The folder where the image will be uploaded.
            image_data (file-like object): The image data to upload.
            filename (str): The name of the file to be uploaded.

        Returns:
            dict: A success message.

        Raises:
            HTTPException: If the specified folders do not exist.
        """
        root_folder = f'{root_folder}/'
        main_folder = f'{root_folder}{main_folder}/'
        upload_image_folder = f'{main_folder}{upload_image_folder}/'

        for folder in [root_folder, main_folder, upload_image_folder]:
            if not await self.folder_exists(folder_key=folder):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{folder} does not exist.')
        
        # Run the upload_fileobj method in a separate thread
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.executor,
            lambda:self.client.upload_fileobj(
                image_data,
                self.bucket_name,
                f'{upload_image_folder}{filename}',
                Config=self.transfer_config
            )
        )

        return "image uploaded successfully"
    
        #This will upload the prdicted images to right folder like blur goes in blur_image_folder and vice versa
    async def upload_smart_share_images(self, root_folder, event_folder, image_data, filename):
        """
        Uploads an image to a specific folder in S3.

        Args:
            root_folder (str): The root folder under which the main and upload folders are located.
            event_name (str): The event folder where the image will be uploaded.
            image_data (file-like object): The image data to upload.
            filename (str): The name of the file to be uploaded.

        Returns:
            dict: A success message.

        Raises:
            HTTPException: If the specified folders do not exist.
        """
        root_folder = f'{root_folder}/'
        event_folder = f'{root_folder}{event_folder}/'

        if not await self.folder_exists(root_folder):
            raise HTTPException(f'Root folder "{root_folder}" does not exist.')
        
        if not await self.folder_exists(event_folder):
            raise HTTPException(f'Event with name "{event_folder}" does not exist.')

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.executor,
            lambda:self.client.upload_fileobj(
                image_data,
                self.bucket_name,
                f'{event_folder}{filename}'
            )
        )
        return {"image uploaded successfully"}
    


    async def get_image_from_s3_before_cull(self, root_folder, main_folder, images_before_cull_folder ,image_key):
        """
        Retrieves an image from S3 before culling.

        Args:
            root_folder (str): The root folder under which the main and images folders are located.
            main_folder (str): The main folder containing the images folder.
            images_before_cull_folder (str): The folder containing images before culling.
            image_key (str): The key of the image to retrieve.

        Returns:
            bytes: The image data.

        Raises:
            Exception: If the specified folders do not exist.
            HTTPException: If the image is not found or there is an error retrieving it.
        """
        root_folder = f'{root_folder}/'
        main_folder = f'{root_folder}{main_folder}/'
        images_before_cull_folder = f'{main_folder}{images_before_cull_folder}/'
        image_key = f'{images_before_cull_folder}/{image_key}'

        for folder in [root_folder, main_folder, images_before_cull_folder]:
            if not await self.folder_exists(folder):
                raise HTTPException(status_code=400, detail=f'{folder} does not exist.')
        
        loop = asyncio.get_running_loop()
        #get image from s3
        try:
            # Run the synchronous S3 get_object call in the executor
            response = await loop.run_in_executor(
                self.executor,
                lambda:self.client.get_object(
                    Bucket=self.bucket_name,
                    Key=image_key
                )
            )
            image_data = response['Body'].read()
        except self.client.exceptions.NoSuchKey:
            raise HTTPException(status_code=404, detail="Image not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return image_data
    

    #it will generate a specific url which is valid for 30 min by default from which you can download image
    async def generate_presigned_url(self, key, expiration=3600):
        """
        Generates a presigned URL for securely accessing an image in S3.
        Args:
            key (str): The S3 key of the image.
            expiration (int, optional): The expiration time of the URL in seconds. Default is 1800 seconds (30 minutes).
        Returns:
            str: The presigned URL.
        Raises:
            Exception: If there is an error generating the presigned URL.
        """

        loop = asyncio.get_running_loop()
        try:
            url = await loop.run_in_executor(
                self.executor,
                lambda:self.client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': key},
                    ExpiresIn=expiration
                )
            )
            return url
        except ClientError as e:
            raise HTTPException(f"Error generating presigned URL: {str(e)}")
    
    async def download_s3_folder(self, prefix):
        loop = asyncio.get_running_loop()

        try:
            folder_list = await loop.run_in_executor(
                self.executor,
                lambda: self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            )
            for contents in folder_list['Contents']:
                all_folder_list = []
                # if contents['Key'] 


            return contents

        except ClientError as e:
            raise Exception(f"Error from s3: {str(e)}")