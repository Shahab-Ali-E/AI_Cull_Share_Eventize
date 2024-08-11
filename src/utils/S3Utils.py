import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException

class S3Utils:
    """
    Initializes the S3Utils class with AWS credentials and bucket information.

    Args:
        aws_region (str): The AWS region where the S3 bucket is located.
        aws_access_key_id (str): The AWS access key ID.
        aws_secret_access_key (str): The AWS secret access key.
        bucket_name (str): The name of the S3 bucket.
    """
    def __init__(self, aws_region, aws_access_key_id, aws_secret_access_key, bucket_name):
        self.bucket_name = bucket_name
        self.client = boto3.client(
            service_name="s3",
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
    
    #It check if that folder already exsists which you want to create
    def folder_exists(self, folder_key):
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
            response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=folder_key, Delimiter='/')
            if 'Contents' in response:
                return True
            return False
        except ClientError as e:
            raise HTTPException(f"Unable to check folder existence: {e}")
    
    #It create an object like folder/uplaod images etc in the bucket
    def create_object(self, folder_key):
        """
        Creates an object (folder or file) in the specified S3 bucket.

        Args:
            folder_key (str): The S3 key of the folder or object to create.
        """
        self.client.put_object(Bucket=self.bucket_name, Key=folder_key)

    #It will delete an Object from S3
    def delete_object(self, folder_key):
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
            objects_to_delete = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=folder_key)

            # Check if there are objects to delete
            if 'Contents' in objects_to_delete:
                delete_keys = [{'Key':obj['Key']} for obj in objects_to_delete['Contents']]
                
                # Delete all objects
                return self.client.delete_objects(Bucket=self.bucket_name, Delete={'Objects': delete_keys})
            else:
                return {"message":"No objects found to delete in S3"}

        except ClientError as e:
            raise HTTPException(status_code=400, detail=f"Unable to delete folder: {e}")
        
        
    #It is use to create folder when all images are ready to cull and user starts culling
    def create_folders_for_culling(self, root_folder, main_folder, images_before_cull_folder, blur_img_folder, closed_eye_img_folder, duplicate_img_folder, fine_collection_img_folder):
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
        
        if not self.folder_exists(root_folder):
            self.create_object(root_folder)
        
        if self.folder_exists(main_folder):
            raise Exception(f'Main folder "{main_folder}" already exists.')
        else:
            self.create_object(main_folder)

        images_before_culling_start = f'{main_folder}{images_before_cull_folder}/'
        blur_folder = f'{main_folder}{blur_img_folder}/'
        closed_eye_folder = f'{main_folder}{closed_eye_img_folder}/'
        duplicate_folder = f'{main_folder}{duplicate_img_folder}/'
        fine_collection_folder = f'{main_folder}{fine_collection_img_folder}/'

        #creating folder here
        self.create_object(images_before_culling_start)
        self.create_object(blur_folder)
        self.create_object(closed_eye_folder)
        self.create_object(duplicate_folder)
        self.create_object(fine_collection_folder)
    

    #It is use to create event folder for smart share where user uploads images
    def create_folders_for_smart_share(self, root_folder, event_name):
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

        if not self.folder_exists(root_folder):
            self.create_object(root_folder)
        
        if self.folder_exists(event_name):
            raise Exception(f'Event with name "{event_name}" already exists.')
        else:
            self.create_object(event_name)
        
        
    #This will upload the prdicted images to right folder like blur goes in blur_image_folder and vice versa
    def upload_image(self, root_folder, main_folder, upload_image_folder, image_data, filename):
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

        if not self.folder_exists(root_folder):
            raise HTTPException(f'Root folder "{root_folder}" does not exist.')
        
        if not self.folder_exists(main_folder):
            raise HTTPException(f'Main folder "{main_folder}" does not exist.')
        
        if not self.folder_exists(upload_image_folder):
            raise HTTPException(f'Upload folder "{upload_image_folder}" does not exist.')

        self.client.upload_fileobj(image_data, self.bucket_name, f'{upload_image_folder}{filename}')

        return {"image uploaded successfully"}
    


    def get_image_from_s3_before_cull(self, root_folder, main_folder, images_before_cull_folder ,image_key):
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

        if not self.folder_exists(self.bucket_name, root_folder):
            raise Exception(f'Root folder "{root_folder}" does not exist.')
        
        if not self.folder_exists(self.bucket_name, main_folder):
            raise Exception(f'Main folder "{main_folder}" does not exist.')
        
        if not self.folder_exists(self.bucket_name, images_before_cull_folder):
            raise Exception(f'Upload folder "{images_before_cull_folder}" does not exist.')
        
        #get image from s3
        try:
            image_data =  self.client.get_object(Bucket=self.bucket_name, key=image_key)['Body'].read()
        except self.client.exceptions.NoSuchKey:
            raise HTTPException(status_code=404, detail="Image not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return image_data
    

    #it will generate a specific url which is valid for 30 min by default from which you can download image
    def generate_presigned_url(self, key, expiration=1800):
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
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            raise Exception(f"Error generating presigned URL: {str(e)}")
