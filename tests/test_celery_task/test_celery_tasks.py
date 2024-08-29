import pytest
from unittest.mock import patch, MagicMock
from celery.result import AsyncResult
from ...src.services.Culling.tasks.cullingTask import get_images_from_aws, blur_image_separation, closed_eye_separation, bulk_save_image_metadata_db, culling_task
from utils.CustomExceptions import URLExpiredException

@pytest.mark.asyncio
@patch('requests.get')
def test_get_images_from_aws(mock_requests_get):
    # Mock the response content
    mock_response = mock_requests_get.return_value
    mock_response.content = b'image content'
    
    # Run the Celery task
    task = get_images_from_aws.s(['http://example.com/image.jpg']).apply()
    
    # Mock the image URL and response
    result = task.get(timeout=10)
    
    # Assert the result
    assert len(result) == 1
    assert result[0]['name'] == 'image.jpg'
    assert result[0]['content'] == b'image content'

@pytest.mark.asyncio
@patch('services.Culling.separateBlurImages.separate_blur_images', return_value=['non-blur-image'])
@patch('Celery.tasks.s3_utils')  # Mock S3Utils
def test_blur_image_separation(mock_s3_utils, mock_separate_blur_images):
    mock_s3_utils.upload_image = MagicMock()
    
    # Run the Celery task
    task = blur_image_separation.s(['image1', 'image2'], 'user123', 'folder', 1).apply()
    
    # Assert the result
    result = task.get(timeout=10)
    assert result == ['non-blur-image']

@pytest.mark.asyncio
@patch('services.Culling.separateClosedEye.ClosedEyeDetection.separate_closed_eye_images_and_upload_to_s3', return_value={'status': 'success'})
@patch('Celery.tasks.s3_utils')  # Mock S3Utils
def test_closed_eye_separation(mock_s3_utils, mock_separate_closed_eye):
    mock_s3_utils.upload_image = MagicMock()
    
    # Mock output from blur separation
    output_from_blur = (['non-blur-image'], [], {})
    
    # Run the Celery task
    task = closed_eye_separation.s(output_from_blur, 'user123', 'folder', 1).apply()
    
    # Assert the result
    result = task.get(timeout=10)
    assert result == {'status': 'success'}

@pytest.mark.asyncio
@patch('Celery.tasks.bulk_save_image_metadata_db', return_value="All metadata has been successfully saved to the database.")
def test_bulk_save_image_metadata_db(mock_bulk_save_image_metadata_db):
    # Mock image metadata
    images_metadata = {'status': 'success'}
    
    # Run the Celery task
    task = bulk_save_image_metadata_db.s(images_metadata).apply()
    
    # Assert the result
    result = task.get(timeout=10)
    assert result == "All metadata has been successfully saved to the database."

@pytest.mark.asyncio
@patch('Celery.tasks.get_images_from_aws')
@patch('Celery.tasks.blur_image_separation')
@patch('Celery.tasks.closed_eye_separation')
@patch('Celery.tasks.bulk_save_image_metadata_db')
@patch('Celery.tasks.chain')
def test_culling_task(mock_chain, mock_bulk_save, mock_closed_eye, mock_blur, mock_get_images):
    # Mock the results of each task
    mock_get_images.return_value = ['mock_image']
    mock_blur.return_value = ['non_blur_image']
    mock_closed_eye.return_value = {'status': 'success'}
    mock_bulk_save.return_value = "All metadata has been successfully saved to the database."
    
    # Mock the chain to return a mock AsyncResult
    mock_result = MagicMock()
    mock_result.id = 'mock_task_id'
    mock_result.parent = None
    mock_chain.return_value.apply_async.return_value = mock_result
    
    # Run the Celery task
    task = culling_task.s('user123', ['url1'], 'folder', 1).apply()
    
    # Assert the result
    result = task.get(timeout=10)
    assert result == {'task_ids': ['mock_task_id']}
