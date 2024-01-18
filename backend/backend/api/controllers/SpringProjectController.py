from api.models import ClassRoom, ClassMember
from api.models import ClassRoom, Team, SpringProject, SpringProjectBoard, ClassMember
from django.shortcuts import render
from django.http import HttpResponse
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from api.serializers import SpringProjectBoardSerializer, SpringProjectSerializer
from api.models import SpringProject, SpringProjectBoard, SpringBoardTemplate, Team, TeamMember
from django.db.models import Max
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

class ProjectCreateView(generics.CreateAPIView):
    # Return all projects and create
    queryset = SpringProject.objects.all()
    serializer_class = SpringProjectSerializer

    def perform_create(self, serializer):
        serializer.save()  

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProjectView(generics.ListAPIView):
    # Get all Projects
    queryset = SpringProject.objects.all()
    serializer_class = SpringProjectSerializer


class GetProjectsByTeamId(generics.ListAPIView):
    # Get all projects of the group
    serializer_class = SpringProjectSerializer
    queryset = SpringProject.objects.all()

    def get(self, request, *args, **kwargs):
        team_id = self.kwargs.get('team_id')
        try:
            projects = SpringProject.objects.filter(team_id=team_id)
            serializer = SpringProjectSerializer(projects, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except SpringProject.DoesNotExist:
            return Response({"error": "Projects not found"}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GetProjectById(generics.ListAPIView):
    # Get project by id
    serializer_class = SpringProjectSerializer
    queryset = SpringProject.objects.all()

    def get(self, request, *args, **kwargs):
        project_id = self.kwargs.get('project_id')

        try:
            projects = SpringProject.objects.get(id=project_id)
            serializer = SpringProjectSerializer(projects)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except SpringProject.DoesNotExist:
            return Response({"error": "Projects not found"}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProjectUpdateView(generics.UpdateAPIView):
    serializer_class = SpringProjectSerializer
    queryset = SpringProject.objects.all()

    def put(self, request, *args, **kwargs):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(SpringProject, pk=project_id)

        serializer = self.get_serializer(project, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteProjectView(generics.DestroyAPIView):
    queryset = SpringProject.objects.all()
    serializer_class = SpringProjectSerializer

    def destroy(self, request, *args, **kwargs):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(SpringProject, pk=project_id)
        project.delete()

        return Response({"message": "Project deleted successfully"}, status=status.HTTP_204_NO_CONTENT)




class GetAllClassroomTeamAndProjects(APIView):
    # Gets all the Groups that belongs to the classroom. This returns:
    # the classroom name, list of groups (group name and list of projects),
    # list of projects per group that are active with the average scores of each board
    def get(self, request):
        try:
            all_data = []
            classrooms = ClassRoom.objects.all()

            for classroom in classrooms:
                class_members = ClassMember.objects.filter(class_id=classroom)
                teacher_info = None

                for class_member in class_members:
                    if class_member.role == 0:
                        teacher_info = f"{class_member.user_id.first_name} {class_member.user_id.last_name}"

                team_ids = TeamMember.objects.filter(class_member_id__in=class_members).values_list('team_id', flat=True).distinct()
                teams = Team.objects.filter(id__in=team_ids)

                for team in teams:
                    team_name = team.name

                    projects_data = []
                    projects = SpringProject.objects.filter(team_id=team.id)

                    for project in projects:
                        project_boards = SpringProjectBoard.objects.filter(project_id=project.id
                        ).values('template_id').annotate(
                            latest_id=Max('id')
                        ).values('latest_id')

                        project_board_data = []

                        for board_data in project_boards:
                            board = SpringProjectBoard.objects.get(
                                id=board_data['latest_id'])
                            board_score = (
                                (board.novelty * 0.4) + (board.technical_feasibility * 0.3) + (board.capability * 0.3))
                            project_board_data.append({
                                "id": f"{team.id}-{project.id}-{board.id}",
                                "board_score": board_score,
                                "template_id": board.template_id
                            })

                        projects_data.append({
                            "project_id": project.id,
                            "project_name": project.name,
                            "project_description": project.description,
                            "project_is_active": project.is_active,
                            "project_score": project.score,
                            "project_reason": project.reason,
                            "project_date_created": project.date_created,
                            "project_boards": project_board_data
                        })
                        
                    for project_data in projects_data:
                        team_info = {
                            "classroom_id": classroom.id,
                            "course_name": classroom.course_name,
                            "sections": classroom.sections,
                            "teacher_info": teacher_info,
                            "team_name": team_name,
                            "projects": [project_data]
                        }

                        all_data.append(team_info)
                        
                    if not projects_data:
                        team_info = {
                            "classroom_id": classroom.id,
                            "course_name": classroom.course_name,
                            "sections": classroom.sections,
                            "teacher_info": teacher_info,
                            "team_name": team_name,
                            "projects": []
                        }

                        all_data.append(team_info)

            return Response(all_data, status=status.HTTP_200_OK)

        except ClassRoom.DoesNotExist:
            return Response({"error": "Classrooms not found"}, status=status.HTTP_404_NOT_FOUND)


class GetTeamsAndProjectsByClassId(APIView):
    def get(self, request, class_id):
        try:
            all_data = []
            classroom = ClassRoom.objects.get(id=class_id)

            class_members = ClassMember.objects.filter(class_id=classroom)

            team_ids = TeamMember.objects.filter(
                class_member_id__in=class_members).values_list('team_id', flat=True).distinct()
            teams = Team.objects.filter(id__in=team_ids)

            for team in teams:
                team_name = team.name

                projects = SpringProject.objects.filter(
                    team_id=team.id, is_active=True)

                if not projects:
                    team_info = {
                        "team_name": team_name,
                        "projects": []
                    }
                    all_data.append(team_info)
                else:
                    for project in projects:
                        project_boards = SpringProjectBoard.objects.filter(
                            project_id=project.id
                        ).values('template_id').annotate(
                            latest_id=Max('id')
                        ).values('latest_id')

                        project_board_data = []

                        for board_data in project_boards:
                            board = SpringProjectBoard.objects.get(
                                id=board_data['latest_id'])
                            board_score = (
                                (board.novelty * 0.4) + (board.technical_feasibility * 0.3) + (board.capability * 0.3))
                            project_board_data.append({
                                "id": f"{team.id}-{project.id}-{board.id}",
                                "board_score": board_score,
                                "template_id": board.template_id
                            })

                        project_data = {
                            "project_id": project.id,
                            "project_name": project.name,
                            "project_description": project.description,
                            "project_is_active": project.is_active,
                            "project_score": project.score,
                            "project_reason": project.reason,
                            "project_date_created": project.date_created,
                            "project_boards": project_board_data
                        }

                        team_info = {
                            "team_name": team_name,
                            "projects": [project_data]
                        }

                        all_data.append(team_info)

            return Response(all_data, status=status.HTTP_200_OK)

        except ClassRoom.DoesNotExist:
            return Response({"error": "Classroom not found"}, status=status.HTTP_404_NOT_FOUND)
