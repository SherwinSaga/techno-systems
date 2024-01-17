from rest_framework import viewsets, mixins, permissions, status
from rest_framework.decorators import action
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from api.custom_permissions import IsTeacher

from api.models import Activity
from api.models import ActivityTemplate
from api.models import ClassRoom
from api.models import Team

from api.serializers import ActivitySerializer
from api.serializers import ActivityTemplateSerializer
from api.serializers import ActivityCreateFromTemplateSerializer
from api.serializers import ClassRoomSerializer
from api.serializers import TeamSerializer

class ActivityController(viewsets.GenericViewSet,
                      mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.UpdateModelMixin,
                      mixins.DestroyModelMixin):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    authentication_classes = [JWTAuthentication]

    # def get_permissions(self):
    #     if self.action in ['create', 'create_from_template', 'destroy', 'get_activities_by_class', 
    #                        'get_submitted_activities_by_class', 'add_evaluation', 'delete_evaluation'
    #                        ]:
    #         return [permissions.IsAuthenticated(), IsTeacher()]
    #     else:
    #         return [permissions.IsAuthenticated()]

    @swagger_auto_schema(
        operation_summary="Creates a new activity",
        operation_description="POST /activities",
        request_body=ActivitySerializer,
        responses={
            status.HTTP_201_CREATED: openapi.Response('Created', ActivitySerializer),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request', message='Bad Request. Invalid or missing data in the request.'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized', message='Unauthorized. Authentication required.'),
            status.HTTP_404_NOT_FOUND: openapi.Response('Not Found', message='Not Found. One or more teams not found.'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden', message='Forbidden. You do not have permission to access this resource.'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error', message='Internal Server Error. An unexpected error occurred.'),
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Save the activity without committing to the database
            activity = serializer.save()
            
            # Get the team_ids from the request data (you may want to validate this)
            team_ids = request.data.get('team_id', [])
            
            if team_ids:
                try:
                    teams = Team.objects.filter(pk__in=team_ids)
                    activity.team_id.set(teams)  # Set the many-to-many relationship
                    activity.save()  # Commit the activity to the database with the assigned teams
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                except Team.DoesNotExist:
                    return Response({'error': 'One or more teams not found'}, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({'error': 'Invalid or empty Team IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_summary="Lists all activities of a class",
        operation_description="GET /classes/{class_pk}/activities",
       responses={
            status.HTTP_200_OK: openapi.Response('OK', ActivitySerializer(many=True)),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request', message='Bad Request. Class ID not provided.'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized', message='Unauthorized. Authentication required.'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden', message='Forbidden. You do not have permission to access this resource.'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error', message='Internal Server Error. An unexpected error occurred.'),
        }
    )
    def list(self, request, *args, **kwargs):
        class_id = kwargs.get('class_pk', None)

        if class_id:
            try:
                activities = Activity.objects.filter(classroom_id=class_id)
                serializer = self.get_serializer(activities, many=True)
                return Response(serializer.data)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({'error': 'Class ID not provided'}, status=status.HTTP_400_BAD_REQUEST)
        
    
    @swagger_auto_schema(
    operation_summary="Create activity from template",
    operation_description="POST /classes/{class_pk}/activities/from_template",
    request_body=ActivityCreateFromTemplateSerializer,
    responses={
        status.HTTP_201_CREATED: openapi.Response('Created', ActivitySerializer),
        status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request', message='Bad Request. Invalid or missing data in the request.'),
        status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized', message='Unauthorized. Authentication required.'),
        status.HTTP_404_NOT_FOUND: openapi.Response('Not Found', message='Not Found. Template or Class not found.'),
        status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error', message='Internal Server Error. An unexpected error occurred.'),
    }
    )
    @action(detail=False, methods=['POST'], url_path='from_template')
    def create_from_template(self, request, class_pk=None, pk=None):
        template_id = request.data.get('template_id', None)
        team_ids = request.data.get('team_ids', [])  # Updated to team_ids
        due_date = request.data.get('due_date', None)
        evaluation = request.data.get('evaluation', None)
        total_score = request.data.get('total_score', None)

        if template_id is not None and class_pk is not None:
            try:
                # Retrieve the class
                class_obj = ClassRoom.objects.get(pk=class_pk)

                template = ActivityTemplate.objects.get(pk=template_id)

                # Create a new activity based on the template
                new_activity = Activity.create_activity_from_template(template)

                # Update additional fields, such as the team and other desired fields
                if team_ids:
                    try:
                        teams = Team.objects.filter(pk__in=team_ids)
                        new_activity.team_id.set(teams)  # Set the many-to-many relationship
                    except Team.DoesNotExist:
                        return Response({"error": "One or more teams not found"}, status=status.HTTP_404_NOT_FOUND)

                # Update due_date, evaluation, and total_score
                if due_date:
                    new_activity.due_date = due_date
                if evaluation:
                    new_activity.evaluation = evaluation
                if total_score:
                    new_activity.total_score = total_score

                # Set the class for the new activity
                new_activity.classroom_id = class_obj

                # Save the updated activity
                new_activity.save()

                # Serialize the template and activity
                template_serializer = ActivityTemplateSerializer(template)
                activity_serializer = ActivitySerializer(new_activity)

                return Response(
                    {
                        "success": "Activity created from template",
                        "activity": activity_serializer.data,
                        "template": template_serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
            except (ActivityTemplate.DoesNotExist, ClassRoom.DoesNotExist) as e:
                return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({"error": "Template ID or Class ID not provided"}, status=status.HTTP_400_BAD_REQUEST)


    # @swagger_auto_schema(
    #     operation_summary="Create an activity from a template",
    #     operation_description="POST /activities/from_template/{template_pk}",
    #     responses={
    #     status.HTTP_200_OK: openapi.Response('OK', ActivitySerializer(many=True)),
    #     status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request', message='Bad Request. Either class ID or team ID is missing or invalid.'),
    #     status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized', message='Unauthorized. Authentication required.'),
    #     status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden', message='Forbidden. You do not have permission to access this resource.'),
    #     status.HTTP_404_NOT_FOUND: openapi.Response('Not Found', message='Not Found. Either class or team not found.'),
    #     status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error', message='Internal Server Error. An unexpected error occurred.'),
    # }
    # )    
    # @action(detail=True, methods=['POST'])
    # def from_template(self, request, *args, **kwargs):
    #     template_id = request.data.get('template_id', None)
    #     team_ids = request.data.get('team_ids', [])  # Updated to team_ids
    #     classroom_id = request.data.get('classroom_id', None)
    #     due_date = request.data.get('due_date', None)
    #     evaluation = request.data.get('evaluation', None)
    #     total_score = request.data.get('total_score', None)

    #     if template_id is not None and classroom_id is not None:
    #         try:
    #             template = ActivityTemplate.objects.get(pk=template_id)

    #             # Create a new activity based on the template
    #             new_activity = Activity.create_activity_from_template(template)

    #             # Update additional fields, such as the team and other desired fields
    #             if team_ids:
    #                 try:
    #                     teams = Team.objects.filter(pk__in=team_ids)
    #                     new_activity.team_id.set(teams)  # Set the many-to-many relationship
    #                 except Team.DoesNotExist:
    #                     return Response({"error": "One or more teams not found"}, status=status.HTTP_404_NOT_FOUND)

    #             # Update due_date, evaluation, and total_score
    #             if due_date:
    #                 new_activity.due_date = due_date
    #             if evaluation:
    #                 new_activity.evaluation = evaluation
    #             if total_score:
    #                 new_activity.total_score = total_score

    #             # Save the updated activity
    #             new_activity.save()

    #             # Serialize the template and activity
    #             template_serializer = ActivityTemplateSerializer(template)
    #             activity_serializer = ActivitySerializer(new_activity)

    #             return Response(
    #                 {
    #                     "success": "Activity created from template",
    #                     "activity": activity_serializer.data,
    #                     "template": template_serializer.data
    #                 },
    #                 status=status.HTTP_201_CREATED
    #             )
    #         except ActivityTemplate.DoesNotExist:
    #             return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)
    #     else:
    #         return Response({"error": "Template ID or Classroom ID not provided"}, status=status.HTTP_400_BAD_REQUEST)
    

class TeamActivitiesController(viewsets.GenericViewSet,
                      mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.UpdateModelMixin,
                      mixins.DestroyModelMixin):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    authentication_classes = [JWTAuthentication]

    @swagger_auto_schema(
        operation_summary="Lists all activities of a team",
        operation_description="GET /classes/{class_pk}/teams/{team_pk}/activities",
        responses={
            status.HTTP_200_OK: openapi.Response('OK', ActivitySerializer(many=True)),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden'),
            status.HTTP_404_NOT_FOUND: openapi.Response('Not Found'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error'),
        }
    )
    def list(self, request, class_pk=None, team_pk=None):
        try:
            # Check if both class_id and team_id are provided
            if class_pk is not None and team_pk is not None:
                # Check if the specified class_id and team_id exist
                if not ClassRoom.objects.filter(pk=class_pk).exists():
                    return Response({'error': 'Class not found'}, status=status.HTTP_404_NOT_FOUND)
                
                if not Team.objects.filter(pk=team_pk).exists():
                    return Response({'error': 'Team not found'}, status=status.HTTP_404_NOT_FOUND)

                # Retrieve activities for the specified class_id and team_id
                activities = Activity.objects.filter(classroom_id=class_pk, team_id=team_pk)
                serializer = self.get_serializer(activities, many=True)
                return Response(serializer.data)

            # Check if team_id is not provided
            elif team_pk is None:
                return Response({'error': 'Team ID not provided'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if class_id is not provided
            elif class_pk is None:
                return Response({'error': 'Class ID not provided'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @swagger_auto_schema(
        operation_summary="Lists all submitted activities of a team",
        operation_description="GET /classes/{class_pk}/teams/{team_pk}/submitted_activities",
        responses={
            status.HTTP_200_OK: openapi.Response('OK', ActivitySerializer(many=True)),
            status.HTTP_400_BAD_REQUEST: openapi.Response('Bad Request', message='Bad Request. Either class ID or team ID is missing or invalid.'),
            status.HTTP_401_UNAUTHORIZED: openapi.Response('Unauthorized', message='Unauthorized. Authentication required.'),
            status.HTTP_403_FORBIDDEN: openapi.Response('Forbidden', message='Forbidden. You do not have permission to access this resource.'),
            status.HTTP_404_NOT_FOUND: openapi.Response('Not Found', message='Not Found. Either class or team not found.'),
            status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response('Internal Server Error', message='Internal Server Error. An unexpected error occurred.'),
        }
    )
    @action(detail=True, methods=['GET'])
    def submitted_activities(self, request, class_pk=None, team_pk=None):
        try:
            # Check if both class_id and team_id are provided
            if class_pk is not None and team_pk is not None:
                # Check if the specified class_id and team_id exist
                if not ClassRoom.objects.filter(pk=class_pk).exists():
                    return Response({'error': 'Class not found'}, status=status.HTTP_404_NOT_FOUND)
                
                if not Team.objects.filter(pk=team_pk).exists():
                    return Response({'error': 'Team not found'}, status=status.HTTP_404_NOT_FOUND)

                # Retrieve submitted activities for the specified class_id and team_id
                submitted_activities = Activity.objects.filter(classroom_id=class_pk, team_id=team_pk, submission_status=True)
                serializer = self.get_serializer(submitted_activities, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)

            # Check if team_id is not provided
            elif team_pk is None:
                return Response({'error': 'Team ID not provided'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if class_id is not provided
            elif class_pk is None:
                return Response({'error': 'Class ID not provided'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)