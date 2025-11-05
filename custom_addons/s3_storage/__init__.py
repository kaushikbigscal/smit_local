from . import models

# def uninstall_hook(env):
#     import base64
#
#     try:
#         s3_attachments = env['ir.attachment'].with_context(skip_res_field_check=True).search([
#             ('s3_key', '!=', False)
#         ])
#
#         image_attachments = env['ir.attachment'].with_context(skip_res_field_check=True).search([
#             ('s3_key', '!=', False),
#             ('res_field', 'in', [
#                 'image_128', 'image_256', 'image_512', 'image_1024', 'image_1920',
#                 'avatar_128', 'avatar_256', 'avatar_512', 'avatar_1024', 'avatar_1920'
#             ])
#         ])
#
#         all_attachments = list(set(s3_attachments.ids + image_attachments.ids))
#         s3_attachments = env['ir.attachment'].browse(all_attachments)
#
#         for attachment in s3_attachments:
#             try:
#                 original_name = attachment.name
#                 original_mimetype = attachment.mimetype
#                 original_res_model = attachment.res_model
#                 original_res_id = attachment.res_id
#                 original_res_field = attachment.res_field
#
#                 binary_data = attachment._s3_read_binary(attachment.s3_key)
#
#                 if binary_data:
#                     base64_data = base64.b64encode(binary_data).decode('ascii')
#
#                     try:
#                         new_attachment = env['ir.attachment'].with_context(
#                             attachment_storage='file',
#                             skip_res_field_check=True
#                         ).create({
#                             'name': original_name,
#                             'datas': base64_data,
#                             'mimetype': original_mimetype,
#                             'res_model': original_res_model,
#                             'res_id': original_res_id,
#                             'res_field': original_res_field,
#                             'type': 'binary',
#                         })
#                         attachment.unlink()
#                     except:
#                         attachment.with_context(
#                             attachment_storage='file',
#                             skip_res_field_check=True
#                         ).write({
#                             'datas': base64_data,
#                         })
#                         attachment.write({'s3_key': False})
#                 else:
#                     continue
#
#             except:
#                 continue
#
#         try:
#             env['ir.attachment'].with_context(skip_res_field_check=True).search([]).write({
#                 'presigned_url_cache': False,
#                 'presigned_url_expires': False,
#             })
#         except:
#             pass
#
#         env.cr.commit()
#
#     except:
#         pass


# def uninstall_hook(env):
#     """
#     Most comprehensive approach - handles edge cases with detailed logging
#     """
#     import logging
#     import base64
#
#     _logger = logging.getLogger(__name__)
#
#     try:
#         # Find all S3 attachments - INCLUDING IMAGE ATTACHMENTS
#         s3_attachments = env['ir.attachment'].with_context(skip_res_field_check=True).search([
#             ('s3_key', '!=', False)
#         ])
#
#         # Also search specifically for image attachments that might be missed
#         image_attachments = env['ir.attachment'].with_context(skip_res_field_check=True).search([
#             ('s3_key', '!=', False),
#             ('res_field', 'in', ['image_128', 'image_256', 'image_512', 'image_1024', 'image_1920',
#                                  'avatar_128', 'avatar_256', 'avatar_512', 'avatar_1024', 'avatar_1920'])
#         ])
#
#         _logger.info(f"Found {len(image_attachments)} image attachments specifically")
#
#         # Combine and remove duplicates
#         all_attachments = list(set(s3_attachments.ids + image_attachments.ids))
#         s3_attachments = env['ir.attachment'].browse(all_attachments)
#
#         success_count = 0
#         error_count = 0
#
#         for attachment in s3_attachments:
#             try:
#                 # Store original values
#                 original_name = attachment.name
#                 original_mimetype = attachment.mimetype
#                 original_res_model = attachment.res_model
#                 original_res_id = attachment.res_id
#                 original_res_field = attachment.res_field
#
#                 # Get binary data from S3
#                 binary_data = attachment._s3_read_binary(attachment.s3_key)
#
#                 if binary_data:
#                     # DETAILED LOGGING FOR IMAGE_128 AND OTHER FILES
#                     if original_res_field and ('image_128' in original_res_field or 'avatar_128' in original_res_field):
#                         if original_res_model and original_res_id:
#                             try:
#                                 resource_record = env[original_res_model].browse(original_res_id)
#                                 if resource_record.exists():
#                                     # Try common name fields
#                                     for name_field in ['name', 'display_name', 'title']:
#                                         if hasattr(resource_record, name_field):
#                                             resource_name = getattr(resource_record, name_field)
#                                             break
#                             except:
#                                 pass
#
#                     elif original_res_field and any(
#                             img_field in original_res_field for img_field in ['image_', 'avatar_']):
#
#                         # Get resource name
#                         resource_name = "N/A"
#                         if original_res_model and original_res_id:
#                             try:
#                                 resource_record = env[original_res_model].browse(original_res_id)
#                                 if resource_record.exists():
#                                     # Try common name fields
#                                     for name_field in ['name', 'display_name', 'title']:
#                                         if hasattr(resource_record, name_field):
#                                             resource_name = getattr(resource_record, name_field)
#                                             break
#                             except:
#                                 resource_name = "Failed to retrieve"
#
#                         _logger.info(f"  Resource Name: {resource_name}")
#                         _logger.info(
#                             f"  Binary Data Preview: {base64.b64encode(binary_data[:50]).decode('ascii')[:50]}...")
#                         _logger.info("=" * 60)
#
#                     # Method 1: Try using datas field (recommended)
#                     try:
#                         base64_data = base64.b64encode(binary_data).decode('ascii')
#
#                         # Create a new attachment record to replace the S3 one
#                         new_attachment = env['ir.attachment'].with_context(
#                             attachment_storage='file',
#                             skip_res_field_check=True  # IMPORTANT: Add this for image attachments
#                         ).create({
#                             'name': original_name,
#                             'datas': base64_data,
#                             'mimetype': original_mimetype,
#                             'res_model': original_res_model,
#                             'res_id': original_res_id,
#                             'res_field': original_res_field,
#                             'type': 'binary',
#                         })
#
#                         # Delete the old S3 attachment
#                         attachment.unlink()
#
#                         success_count += 1
#
#                         if original_res_field and (
#                                 'image_128' in original_res_field or 'avatar_128' in original_res_field):
#                             _logger.info(f"✓ SUCCESS: Recreated image_128 attachment {new_attachment.id} in filestore")
#                             _logger.info(f"  New store_fname: {new_attachment.store_fname}")
#                             _logger.info(f"  New file_size: {new_attachment.file_size}")
#                         elif original_res_field and any(
#                                 img_field in original_res_field for img_field in ['image_', 'avatar_']):
#                             _logger.info(
#                                 f"✓ SUCCESS: Recreated image attachment {new_attachment.id} ({original_name}) in filestore")
#                         else:
#                             _logger.info(
#                                 f"✓ SUCCESS: Recreated attachment {new_attachment.id} ({original_name}) in filestore")
#
#                     except Exception as create_error:
#                         _logger.error(f"Failed to recreate attachment {attachment.id}: {create_error}")
#
#                         # Fallback: Try direct update
#                         attachment.with_context(
#                             attachment_storage='file',
#                             skip_res_field_check=True  # IMPORTANT: Add this for image attachments
#                         ).write({
#                             'datas': base64_data,
#                         })
#                         attachment.write({'s3_key': False})
#
#                         success_count += 1
#
#                         if original_res_field and (
#                                 'image_128' in original_res_field or 'avatar_128' in original_res_field):
#                             _logger.info(
#                                 f"✓ FALLBACK SUCCESS: Updated image_128 attachment {attachment.id} to filestore")
#                         elif original_res_field and any(
#                                 img_field in original_res_field for img_field in ['image_', 'avatar_']):
#
#                         else:
#                             _logger.info(
#                                 f"✓ FALLBACK SUCCESS: Updated attachment {attachment.id} ({original_name}) to filestore")
#
#                 else:
#                     _logger.warning(f"No binary data found for attachment {attachment.id}")
#                     error_count += 1
#
#             except Exception as e:
#                 _logger.error(f"Failed to migrate attachment {attachment.id}: {e}")
#                 error_count += 1
#                 continue
#
#         # Clear any cached presigned URLs
#         try:
#             env['ir.attachment'].with_context(skip_res_field_check=True).search([]).write({
#                 'presigned_url_cache': False,
#                 'presigned_url_expires': False,
#             })
#         except:
#             pass
#
#         # Commit the changes
#         env.cr.commit()
#         _logger.info(f"Migration completed: {success_count} successful, {error_count} errors")
#
#
#     except Exception as e:
#         _logger.error(f"Uninstall hook failed: {e}")
#         pass
