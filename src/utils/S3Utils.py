import boto3
from botocore.exceptions import ClientError
import io
from fastapi import HTTPException

class S3Utils:
    def __init__(self, aws_region, aws_access_key_id, aws_secret_access_key, bucket_name):
        self.bucket_name = bucket_name
        self.client = boto3.client(
            service_name="s3",
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
    
    def folder_exists(self, folder_key):
        try:
            response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=folder_key, Delimiter='/')
            if 'Contents' in response:
                return True
            return False
        except ClientError as e:
            raise HTTPException(f"Unable to check folder existence: {e}")
    
    def create_object(self, folder_key):
        self.client.put_object(Bucket=self.bucket_name, Key=folder_key)
    

    #it is use to create folder when all images are ready to cull and user starts culling
    def create_folders_for_culling(self, root_folder, main_folder, images_before_cull_folder, blur_img_folder, closed_eye_img_folder, duplicate_img_folder, fine_collection_img_folder):
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


    #this will upload the prdicted images to right folder like blur goes in blur_image_folder and vice versa
    def upload_image(self, root_folder, main_folder, upload_image_folder, image_data, filename):
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
    
    #it will generate a specific url which is valid for 1 min from which you can download image
    def generate_presigned_url(self, key, expiration=3600):
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            raise Exception(f"Error generating presigned URL: {str(e)}")
